"""Territorios indigenas e quilombolas do RS — quem vive onde a agua volta.

Por que esta camada existe
==========================

A camada de resposta ja registrava, do MUNIC 2024, que comunidades
tradicionais foram atingidas em 2024. Mas registrava como um SIM/NAO por
municipio: nao dizia onde, quantos, nem se o territorio esta na planicie.

Isso importa por uma razao concreta e nao retorica: ribeirinho, quilombola e
indigena ocupam desproporcionalmente varzea e margem — por historia de
ocupacao, nao por acaso. E varzea e exatamente o terreno que a memoria
hidrica do JRC identifica como "ja foi agua". Cruzar os dois responde uma
pergunta que nenhuma outra camada responde: **quem esta morando onde a agua
tem precedente de voltar**.

Fontes
------
`ibge_quilombola`  IBGE, Censo 2022 — territorios quilombolas mapeados.
                   495 no Brasil.
`ibge_indigena`    IBGE, Base Cartografica 250k 2019 — terras indigenas,
                   com grupo etnico e situacao juridica. 448 no Brasil.

DUAS ARMADILHAS DE INTERPRETACAO, DECLARADAS
============================================

1. **Territorio mapeado nao e territorio existente.** Comunidade quilombola
   sem processo aberto, ou terra indigena em estudo, nao aparece com
   poligono. A ausencia no mapa NAO prova ausencia no territorio — e aqui o
   vies e sistematico e conhecido: quem tem menos acesso a Estado tem menos
   chance de estar mapeado. Ler um vazio como "nao ha comunidade" inverte a
   realidade que o dado registra.

2. **`situacaojuridica` importa.** Terra "Regularizada" e "Em estudo" tem o
   mesmo poligono e realidades opostas em conflito fundiario e em acesso a
   politica publica. O campo viaja inteiro; nao e reduzido a um booleano.

E o que este modulo NAO faz: contar pessoas. O poligono nao traz populacao.
Quantas pessoas vivem em cada territorio exige o setor censitario do Censo
2022, que nao esta ingerido.
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
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_INTERIM = REPO_ROOT / "data" / "interim"

BASE = "https://geoservicos.ibge.gov.br/geoserver/ows"
CACHE_HORAS = 24 * 90
INGESTOR_VERSION = "1"

# Caixa do RS em CRS84 (lon, lat).
#
# ATENCAO: usar `EPSG:4326` aqui devolve ZERO feicoes. O GeoServer honra a
# ordem de eixo oficial do EPSG:4326, que e (lat, lon) — e a consulta em
# (lon, lat) cai no oceano Indico. CRS84 e o mesmo datum com ordem (lon, lat)
# explicita, e e o unico que funciona sem ambiguidade.
BBOX_RS = "-57.7,-33.8,-49.6,-27.0,urn:ogc:def:crs:OGC:1.3:CRS84"


@dataclass(frozen=True)
class Camada:
    source_id: str
    layer: str
    rotulo: str
    campo_nome: str
    campo_situacao: str
    notas: str


CAMADAS = [
    Camada(
        source_id="ibge_quilombola",
        # As duas camadas usam nomes de campo diferentes para a mesma coisa:
        # `nm_tq` aqui, `nome` na de terra indigena. Descobrir isso custou uma
        # rodada com 29 territorios sem nome — por isso o campo e declarado
        # por camada em vez de suposto igual.
        layer="CGMAT:qg_2022_620_territorioquilombola__v02",
        rotulo="territorio quilombola",
        campo_nome="nm_tq",
        campo_situacao="status",
        notas="IBGE, Censo 2022. Territorio MAPEADO — comunidade sem processo aberto nao aparece. "
              "`status` distingue TITULADO de etapas anteriores do processo.",
    ),
    Camada(
        source_id="ibge_indigena",
        layer="CCAR:BC250_2019_Terra_Indigena_A",
        rotulo="terra indigena",
        campo_nome="nome",
        campo_situacao="situacaojuridica",
        notas="IBGE BC250 2019. `situacaojuridica` distingue regularizada de em estudo — "
              "mesmo poligono, realidades opostas.",
    ),
]


class IngestError(RuntimeError):
    """Erro de ingestao — a mensagem sempre nomeia fonte + etapa."""


def _get(params: dict[str, str], tentativas: int = 3) -> bytes:
    if os.environ.get("CLIMATE_OFFLINE") == "1":
        raise IngestError("territorios: fetch bloqueado (CLIMATE_OFFLINE=1)")
    url = f"{BASE}?{urllib.parse.urlencode(params)}"
    ultimo: Exception | None = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "climate-rs-engine/1"})
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            ultimo = exc
            if i < tentativas - 1:
                time.sleep(3 * (i + 1))
    raise IngestError(f"territorios: falha na etapa fetch ({url}): {ultimo}")


def _latest_raw_dir(source_id: str) -> Path | None:
    base = DATA_RAW / source_id
    if not base.exists():
        return None
    dirs = sorted((p for p in base.iterdir() if p.is_dir()), reverse=True)
    return dirs[0] if dirs else None


def _baixar(cam: Camada) -> tuple[dict, Path]:
    latest = _latest_raw_dir(cam.source_id)
    if latest is not None and (latest / "payload.geojson").exists():
        prov = json.loads((latest / "provenance.json").read_text(encoding="utf-8"))
        idade = (pd.Timestamp.now(tz="UTC") - pd.Timestamp(prov["fetched_at"])).total_seconds() / 3600
        if idade <= CACHE_HORAS or os.environ.get("CLIMATE_OFFLINE") == "1":
            return json.loads((latest / "payload.geojson").read_text(encoding="utf-8")), latest

    raw = _get({
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": cam.layer,
        "outputFormat": "application/json",
        "bbox": BBOX_RS,
    })
    out_dir = DATA_RAW / cam.source_id / pd.Timestamp.now(tz="UTC").strftime("%Y%m%dT%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "payload.geojson").write_bytes(raw)
    (out_dir / "provenance.json").write_text(
        json.dumps(
            {
                "url": BASE,
                "layer": cam.layer,
                "fetched_at": pd.Timestamp.now(tz="UTC").isoformat(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "product_version": "IBGE GeoServer WFS",
                "ingestor_version": INGESTOR_VERSION,
                "rows": None,
                "notes": cam.notas,
                "bbox": BBOX_RS,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return json.loads(raw.decode("utf-8")), out_dir


def _aneis(geometry: dict) -> list:
    if geometry["type"] == "Polygon":
        return geometry["coordinates"]
    return [anel for poly in geometry["coordinates"] for anel in poly]


def _centroide(geometry: dict) -> tuple[float, float]:
    pts = [p for anel in _aneis(geometry) for p in anel]
    return (
        sum(p[0] for p in pts) / len(pts),
        sum(p[1] for p in pts) / len(pts),
    )


def run() -> pd.DataFrame:
    linhas = []
    for cam in CAMADAS:
        geo, raw_dir = _baixar(cam)
        feats = geo.get("features", [])
        for f in feats:
            props = f.get("properties", {})
            g = f.get("geometry")
            if not g:
                continue
            lon, lat = _centroide(g)
            linhas.append({
                "tipo": cam.rotulo,
                "fonte": cam.source_id,
                "nome": props.get(cam.campo_nome),
                # Grupo etnico so existe na terra indigena; no quilombola vem
                # None e isso e correto — as duas bases nao descrevem a mesma
                # coisa e forcar um campo comum inventaria equivalencia.
                "grupo_etnico": props.get("grupoetnico"),
                "situacao_juridica": props.get(cam.campo_situacao),
                "area_legal_ha": props.get("arealegal"),
                "lon": lon,
                "lat": lat,
                "geometria": json.dumps(g),
            })
        prov_path = raw_dir / "provenance.json"
        if prov_path.exists():
            prov = json.loads(prov_path.read_text(encoding="utf-8"))
            prov["rows"] = len(feats)
            prov_path.write_text(json.dumps(prov, indent=2, ensure_ascii=False), encoding="utf-8")

    df = pd.DataFrame(linhas)
    if df.empty:
        raise IngestError(
            "territorios: nenhuma feicao — confira a ordem de eixo do bbox (CRS84, nao EPSG:4326)"
        )
    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    df.to_parquet(DATA_INTERIM / "territorios_rs.parquet", index=False)
    return df


if __name__ == "__main__":
    d = run()
    print(f"[OK] territorios_rs: {len(d)} territorios no recorte do RS")
    print(d["tipo"].value_counts().to_string())
    ti = d[d.tipo == "terra indigena"]
    if len(ti):
        print("\n  situacao juridica das terras indigenas:")
        print(ti["situacao_juridica"].value_counts().to_string())
        print("\n  grupos etnicos:")
        print(ti["grupo_etnico"].value_counts().head(8).to_string())
    sys.exit(0)
