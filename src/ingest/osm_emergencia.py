"""Bases de emergencia do RS — bombeiros e policia, via OpenStreetMap.

Por que OSM, e o que isso custa
===============================

Nao existe cadastro publico aberto de quarteis do CBMRS nem de unidades da
Brigada Militar com coordenada. O que existe e o OpenStreetMap: colaborativo,
gratuito e com 129 quarteis e 577 unidades policiais mapeados no RS.

O custo e declarado e nao pequeno: **OSM nao e cadastro oficial**. A cobertura
e desigual — um quartel existente e nao mapeado simplesmente nao aparece, e a
ausencia no mapa NAO prova ausencia no territorio. Por isso todo numero desta
fonte sai com `basis: "measured"` (o ponto foi observado por alguem) mas com
`completude: "colaborativa"`, e a interface diz isso ao lado do total.

O que esta fonte NAO da: VIATURA
================================

Isto e base, nao frota. Nao ha dado publico de quantas viaturas cada unidade
opera, de que tipo, nem em que estado. "Realocar viatura" nesta central so
pode significar **onde o vazio de cobertura e maior diante do risco** — nunca
"mova N carros de A para B", que exigiria frota, malha viaria e modelo de
tempo-resposta que nao existem aqui.

A mesma disciplina de "estabelecimento, nunca leito" (ADR-036) vale aqui:
base, nunca viatura.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_INTERIM = REPO_ROOT / "data" / "interim"

SOURCE_ID = "osm_emergencia"
INGESTOR_VERSION = "1"
OVERPASS = "https://overpass-api.de/api/interpreter"
CACHE_HORAS = 24 * 30

# `nwr` cobre node, way e relation: quartel mapeado como area (way) e tao
# valido quanto o mapeado como ponto, e pegar so `node` perderia a maioria dos
# grandes. `out center` devolve o centroide de way/relation.
CONSULTA = """
[out:json][timeout:240];
area["ISO3166-2"="BR-RS"]->.rs;
(
  nwr["amenity"="fire_station"](area.rs);
  nwr["amenity"="police"](area.rs);
  way["bridge"]["highway"~"^(motorway|trunk|primary|secondary)$"](area.rs);
);
out center tags;
"""

PAPEL = {"fire_station": "bombeiro", "police": "policia"}

# Pontes SO na malha principal (motorway, trunk, primary, secondary). A malha
# completa do RS tem dezenas de milhares de travessias, a maioria bueiro de
# estrada vicinal. O recorte responde a pergunta que importa numa cheia:
# quais travessias, se caem, ISOLAM um municipio — e essas estao na malha
# estruturante, nao na vicinal.
#
# ATENCAO ao que este dado NAO e: nao ha estado de conservacao, ano de
# construcao, vao, carga nem laudo. O OSM registra que existe uma ponte ali,
# nao se ela aguenta. "Manutencao de pontoes" nesta central so pode significar
# ONDE INSPECIONAR, nunca "esta ponte precisa de reparo".
HIGHWAY_PRINCIPAL = {"motorway", "trunk", "primary", "secondary"}


class IngestError(RuntimeError):
    """Erro de ingestao — a mensagem sempre nomeia fonte + etapa."""


def _post(consulta: str, tentativas: int = 3) -> bytes:
    if os.environ.get("CLIMATE_OFFLINE") == "1":
        raise IngestError(f"{SOURCE_ID}: fetch bloqueado (CLIMATE_OFFLINE=1)")
    corpo = urllib.parse.urlencode({"data": consulta}).encode()
    ultimo: Exception | None = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(
                OVERPASS,
                data=corpo,
                headers={
                    "User-Agent": "climate-rs-engine/1",
                    # Overpass responde 406 sem isto — o erro nao diz por que.
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            ultimo = exc
            if i < tentativas - 1:
                time.sleep(5 * (i + 1))  # Overpass e compartilhado: recuo generoso
    raise IngestError(f"{SOURCE_ID}: falha na etapa fetch: {ultimo}")


def _latest_raw_dir() -> Path | None:
    base = DATA_RAW / SOURCE_ID
    if not base.exists():
        return None
    dirs = sorted((p for p in base.iterdir() if p.is_dir()), reverse=True)
    return dirs[0] if dirs else None


def parse(raw: bytes) -> pd.DataFrame:
    payload = json.loads(raw.decode("utf-8"))
    linhas = []
    for e in payload.get("elements", []):
        tags = e.get("tags", {})
        amenity = tags.get("amenity")
        via = tags.get("highway")
        ehponte = bool(tags.get("bridge")) and via in HIGHWAY_PRINCIPAL

        if amenity in PAPEL:
            papel = PAPEL[amenity]
        elif ehponte:
            papel = "ponte"
        else:
            continue

        # node traz lat/lon direto; way e relation trazem `center`.
        lat = e.get("lat") or (e.get("center") or {}).get("lat")
        lon = e.get("lon") or (e.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        linhas.append({
            "osm_id": f"{e.get('type')}/{e.get('id')}",
            "papel": papel,
            "nome": tags.get("name"),
            "operador": tags.get("operator"),
            # `via` e `ref` so fazem sentido para ponte: dizem QUAL rodovia cai
            # junto com ela. BR-116 e BR-290 nao sao equivalentes a uma
            # secundaria sem nome.
            "via": via if ehponte else None,
            "ref": tags.get("ref") if ehponte else None,
            "lat": float(lat),
            "lon": float(lon),
        })
    df = pd.DataFrame(linhas)
    if df.empty:
        raise IngestError(f"{SOURCE_ID}: nenhuma base retornada — consulta ou area mudou")
    return df


def run() -> pd.DataFrame:
    latest = _latest_raw_dir()
    usar_cache = False
    if latest is not None and (latest / "payload.json").exists():
        prov = json.loads((latest / "provenance.json").read_text(encoding="utf-8"))
        idade = (pd.Timestamp.now(tz="UTC") - pd.Timestamp(prov["fetched_at"])).total_seconds() / 3600
        usar_cache = idade <= CACHE_HORAS or os.environ.get("CLIMATE_OFFLINE") == "1"

    if usar_cache and latest is not None:
        raw = (latest / "payload.json").read_bytes()
        raw_dir = latest
    else:
        raw = _post(CONSULTA)
        raw_dir = DATA_RAW / SOURCE_ID / pd.Timestamp.now(tz="UTC").strftime("%Y%m%dT%H%M%S")
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "payload.json").write_bytes(raw)
        (raw_dir / "provenance.json").write_text(
            json.dumps(
                {
                    "url": OVERPASS,
                    "fetched_at": pd.Timestamp.now(tz="UTC").isoformat(),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "product_version": "OpenStreetMap via Overpass",
                    "ingestor_version": INGESTOR_VERSION,
                    "rows": None,
                    "notes": (
                        "Quarteis de bombeiro, unidades policiais e pontes da malha principal "
                        "do RS. Base COLABORATIVA, nao cadastro oficial: ausencia no mapa nao "
                        "prova ausencia no territorio. E BASE, nunca viatura, e para pontes e "
                        "EXISTENCIA, nunca estado de conservacao."
                    ),
                    "consulta": CONSULTA.strip(),
                    "licenca": "ODbL — OpenStreetMap contributors",
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    df = parse(raw)
    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    df.to_parquet(DATA_INTERIM / f"{SOURCE_ID}.parquet", index=False)

    prov_path = raw_dir / "provenance.json"
    if prov_path.exists():
        prov = json.loads(prov_path.read_text(encoding="utf-8"))
        prov["rows"] = len(df)
        prov_path.write_text(json.dumps(prov, indent=2, ensure_ascii=False), encoding="utf-8")
    return df


if __name__ == "__main__":
    d = run()
    print(f"[OK] {SOURCE_ID}: {len(d)} bases")
    print(d["papel"].value_counts().to_string())
    print(f"     com nome: {int(d['nome'].notna().sum())} · sem nome: {int(d['nome'].isna().sum())}")
    sys.exit(0)
