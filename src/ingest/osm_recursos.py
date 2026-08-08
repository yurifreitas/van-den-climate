"""Recursos de apoio do RS via OpenStreetMap — o que sustenta a resposta.

A pergunta que faltava
======================

A central ja sabia onde estao hospital, quartel e delegacia. Numa cheia,
porem, o que decide a semana seguinte quase nunca e o quartel: e onde as
pessoas dormem quando saem de casa, se ha combustivel para o caminhao chegar,
se a subestacao que alimenta a casa de bomba esta na cota que alaga, e se o
heliponto mais proximo fica a 40 km da unica cidade que ficou ilhada.

Maio de 2024 deixou isso explicito no RS: escolas e ginasios viraram abrigo,
postos ficaram sem bomba porque ficaram sem energia, e o resgate por
helicoptero foi limitado por onde dava para pousar. Nenhuma dessas coisas
estava mapeada nesta engine.

O QUE ENTRA, E COMO CADA COISA DEVE SER LIDA
============================================

    abrigo_escola        escola — o abrigo de fato usado no RS em 2024
    abrigo_comunitario   centro comunitario e ginasio/centro esportivo
    abrigo_religioso     templo de qualquer culto
    heliponto            helipad e heliporto
    aerodromo            pista registrada no mapa
    energia_subestacao   subestacao de energia
    agua_tratamento      estacao de tratamento / captacao
    agua_reservatorio    caixa d'agua elevada e tanque de armazenamento
    combustivel          posto de combustivel
    alimento             supermercado

ABRIGO AQUI E POTENCIAL, NUNCA CADASTRO
=======================================

Esta e a ressalva mais importante do modulo, e ela nao e formalidade.

Um ginasio no mapa e um predio grande e coberto. Ele NAO declara capacidade,
nao diz se tem banheiro suficiente, cozinha, acessibilidade, gerador ou
sequer se o municipio pretende usa-lo. A lista de abrigos de verdade e
decisao da Defesa Civil municipal, atualizada no evento, e nao existe em base
publica aberta para o RS.

Entao o numero daqui responde "quantos predios grandes e cobertos ha na
cidade", que e um PISO de possibilidade — util para achar o municipio que nao
tem nenhum, inutil para planejar ocupacao. Qualquer soma de "vagas de abrigo"
a partir disto seria inventada, e por isso o modulo nao emite capacidade em
nenhum campo.

O QUE VALE PARA TODAS AS CLASSES
================================

OSM e colaborativo. Ausencia no mapa nao prova ausencia no territorio, e a
cobertura e desigual entre cidade grande e interior — o que enviesa
exatamente na direcao errada, porque o interior mal mapeado e tambem o que
tem menos recurso de verdade. Todo numero sai `measured` (alguem observou
aquele ponto) com `completude: colaborativa`.

Licenca ODbL: exige atribuicao visivel em obra derivada publicada. E
obrigacao legal, nao cortesia.
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

SOURCE_ID = "osm_recursos"
INGESTOR_VERSION = "1"
OVERPASS = "https://overpass-api.de/api/interpreter"
CACHE_HORAS = 24 * 30

# `nwr` cobre node, way e relation: escola mapeada como area e tao valida
# quanto a mapeada como ponto — e as grandes sao quase sempre area.
CONSULTA = """
[out:json][timeout:600];
area["ISO3166-2"="BR-RS"]->.rs;
(
  nwr["amenity"="school"](area.rs);
  nwr["amenity"="community_centre"](area.rs);
  nwr["leisure"="sports_centre"](area.rs);
  nwr["amenity"="place_of_worship"](area.rs);
  nwr["aeroway"~"^(helipad|heliport|aerodrome)$"](area.rs);
  nwr["power"="substation"](area.rs);
  nwr["man_made"~"^(water_works|water_tower|storage_tank)$"](area.rs);
  nwr["amenity"="fuel"](area.rs);
  nwr["shop"="supermarket"](area.rs);
);
out center tags;
"""


def _papel(tags: dict) -> tuple[str, str | None] | None:
    """(papel, subtipo) a partir das tags, ou None se a feicao nao serve.

    A ordem dos testes segue a especificidade: `aeroway` antes de `amenity`
    porque um heliporto de hospital carrega os dois, e a informacao util ali
    e que da para pousar.
    """
    aero = tags.get("aeroway")
    if aero in ("helipad", "heliport"):
        return "heliponto", aero
    if aero == "aerodrome":
        return "aerodromo", tags.get("aerodrome:type")

    if tags.get("power") == "substation":
        return "energia_subestacao", tags.get("substation")

    mm = tags.get("man_made")
    if mm == "water_works":
        return "agua_tratamento", None
    if mm in ("water_tower", "storage_tank"):
        # Tanque de armazenamento so entra se for de agua: o mesmo tag cobre
        # tanque de combustivel e de efluente, e contar os tres juntos como
        # reserva de agua seria afirmar autonomia que nao existe.
        conteudo = tags.get("content")
        if mm == "storage_tank" and conteudo not in ("water", "drinking_water", None):
            return None
        return "agua_reservatorio", mm

    amenity = tags.get("amenity")
    if amenity == "school":
        return "abrigo_escola", tags.get("isced:level") or tags.get("school:type")
    if amenity == "community_centre":
        return "abrigo_comunitario", "community_centre"
    if amenity == "place_of_worship":
        return "abrigo_religioso", tags.get("religion")
    if amenity == "fuel":
        return "combustivel", None

    if tags.get("leisure") == "sports_centre":
        return "abrigo_comunitario", "sports_centre"
    if tags.get("shop") == "supermarket":
        return "alimento", "supermarket"
    return None


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
                    # Sem este header o Overpass responde 406 e nao diz por que.
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            with urllib.request.urlopen(req, timeout=700) as r:
                return r.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            ultimo = exc
            if i < tentativas - 1:
                time.sleep(10 * (i + 1))   # instancia publica compartilhada
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
        classificado = _papel(tags)
        if classificado is None:
            continue
        papel, subtipo = classificado
        lat = e.get("lat") or (e.get("center") or {}).get("lat")
        lon = e.get("lon") or (e.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        linhas.append({
            "osm_id": f"{e.get('type')}/{e.get('id')}",
            "papel": papel,
            "subtipo": subtipo,
            "nome": tags.get("name"),
            "operador": tags.get("operator"),
            "lat": float(lat),
            "lon": float(lon),
        })
    df = pd.DataFrame(linhas)
    if df.empty:
        raise IngestError(f"{SOURCE_ID}: nenhum recurso retornado — consulta ou area mudou")
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
                        "Abrigo potencial (escola, ginasio, templo), heliponto, aerodromo, "
                        "subestacao, agua, combustivel e supermercado. Base COLABORATIVA. "
                        "ABRIGO E POTENCIAL: predio grande e coberto, sem capacidade "
                        "declarada — a lista real e da Defesa Civil municipal e nao existe "
                        "em base publica aberta."
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
    print(f"[OK] {SOURCE_ID}: {len(d)} recursos")
    print(d["papel"].value_counts().to_string())
    print(f"     com nome: {int(d['nome'].notna().sum())} · sem nome: {int(d['nome'].isna().sum())}")
    sys.exit(0)
