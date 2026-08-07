"""Mapa geral de recursos de resposta e os vazios de cobertura.

A pergunta
==========

"Onde estao os recursos, e onde falta?" — e, a partir dai, onde realocar antes
da temporada.

O que entra
===========

    fixo_hospitalar   hospital geral e especializado (CNES)
    fixo_urgencia     pronto-socorro e pronto-atendimento (CNES)
    movel             unidade movel terrestre (CNES) — ver ressalva abaixo
    regulacao         central de regulacao de urgencia / SAMU (CNES)
    psicossocial      CAPS e residencial terapeutico (CNES)
    bombeiro          quartel (OpenStreetMap)
    policia           unidade policial (OpenStreetMap)

TRES RESSALVAS QUE MUDAM A LEITURA
==================================

1. **Base, nunca viatura.** Nao ha dado publico de frota — nem de ambulancia,
   nem de viatura policial, nem de caminhao de bombeiro. "Realocar viatura"
   aqui so pode significar *onde o vazio de cobertura e maior diante do
   risco*. Dizer "mova N carros de A para B" exigiria frota, malha viaria e
   modelo de tempo-resposta, e nenhum dos tres existe nesta engine.

2. **O CNES nao registra a frota do SAMU.** As unidades moveis cadastradas no
   RS somam 205, das quais so 31 se identificam por nome como ambulancia,
   resgate ou bombeiro — o resto e unidade odontologica, farmacia movel e
   saude movel. A frota real do SAMU e operada sob o CNES da central de
   regulacao, nao registrada uma a uma. As 7 centrais sao o sinal confiavel
   de cobertura SAMU; a contagem de moveis NAO e.

3. **Bombeiro e policia vem do OpenStreetMap**, que e colaborativo. Quartel
   existente e nao mapeado nao aparece, e ausencia no mapa NAO prova ausencia
   no territorio. Um vazio aqui e hipotese de vazio, e a interface diz isso.

Distancia
=========

Haversine sobre centroide municipal: linha reta, nao rota. Em cheia a
diferenca entre uma e outra e exatamente o problema — a distancia real cresce
e as vezes vira infinita quando a rodovia corta. O numero aqui e um PISO da
dificuldade de acesso, nunca uma estimativa de tempo.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
INTERIM = REPO_ROOT / "data" / "interim"

CNES_PARQUET = INTERIM / "cnes_rs.parquet"
OSM_PARQUET = INTERIM / "osm_emergencia.parquet"
MALHA_GEOJSON = INTERIM / "ibge_malha_rs.geojson"

VERSION = "recursos-v1"

# Papeis e como cada um deve ser lido. `completude` distingue cadastro oficial
# de mapeamento colaborativo — sem isso, um vazio do OSM parece um vazio real.
PAPEIS: dict[str, dict[str, Any]] = {
    "fixo_hospitalar": {"label": "Hospital", "fonte": "cnes_rs", "completude": "cadastro"},
    "fixo_urgencia": {"label": "Pronto-socorro / atendimento", "fonte": "cnes_rs", "completude": "cadastro"},
    "regulacao": {"label": "Central de regulacao (SAMU)", "fonte": "cnes_rs", "completude": "cadastro"},
    "psicossocial": {"label": "CAPS e residencial terapeutico", "fonte": "cnes_rs", "completude": "cadastro"},
    "movel": {"label": "Unidade movel terrestre", "fonte": "cnes_rs", "completude": "cadastro_parcial"},
    "bombeiro": {"label": "Quartel de bombeiros", "fonte": "osm_emergencia", "completude": "colaborativa"},
    "policia": {"label": "Unidade policial", "fonte": "osm_emergencia", "completude": "colaborativa"},
}

# Papeis cuja ausencia vira acao no plano. `movel` fica de fora: a contagem
# nao e confiavel (ver ressalva 2) e um vazio ali nao sustenta recomendacao.
PAPEIS_CRITICOS = ("fixo_urgencia", "bombeiro", "psicossocial")

# Distancia a partir da qual o vazio deixa de ser geografia e vira problema
# operacional. 30 km em linha reta ja significa, em estrada de interior,
# tempo de resposta acima do que qualquer protocolo de urgencia aceita.
LIMIAR_VAZIO_KM = 30.0


def _aneis(geometry: dict) -> list[list[list[float]]]:
    if geometry["type"] == "Polygon":
        return geometry["coordinates"]
    return [anel for poly in geometry["coordinates"] for anel in poly]


def _centroides() -> dict[int, tuple[float, float]]:
    geo = json.loads(MALHA_GEOJSON.read_text(encoding="utf-8"))
    out: dict[int, tuple[float, float]] = {}
    for f in geo["features"]:
        pts = [p for anel in _aneis(f["geometry"]) for p in anel]
        out[int(f["properties"]["codarea"])] = (
            float(np.mean([p[0] for p in pts])),
            float(np.mean([p[1] for p in pts])),
        )
    return out


def _haversine(lon1: float, lat1: float, lon2: np.ndarray, lat2: np.ndarray) -> np.ndarray:
    r = 6371.0
    p1, p2 = math.radians(lat1), np.radians(lat2)
    a = (
        np.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * r * np.arcsin(np.sqrt(a))


@dataclass(frozen=True)
class RecursosResult:
    pontos: list[dict[str, Any]]
    por_municipio: dict[int, dict[str, Any]]
    resumo: dict[str, Any]


def _carregar_pontos() -> pd.DataFrame:
    quadros = []
    if CNES_PARQUET.exists():
        c = pd.read_parquet(CNES_PARQUET)
        c = c.dropna(subset=["lat", "lon"])
        quadros.append(pd.DataFrame({
            "id": c["codigo_cnes"].astype(str),
            "papel": c["papel"],
            "nome": c["nome_fantasia"],
            "subtipo": c.get("subtipo"),
            "lat": c["lat"].astype(float),
            "lon": c["lon"].astype(float),
            "fonte": "cnes_rs",
        }))
    if OSM_PARQUET.exists():
        o = pd.read_parquet(OSM_PARQUET)
        quadros.append(pd.DataFrame({
            "id": o["osm_id"],
            "papel": o["papel"],
            "nome": o["nome"],
            "subtipo": None,
            "lat": o["lat"].astype(float),
            "lon": o["lon"].astype(float),
            "fonte": "osm_emergencia",
        }))
    if not quadros:
        raise FileNotFoundError(
            "Nenhuma base de recursos ingerida — rode `python -m src.ingest.cnes_rs` "
            "e `python -m src.ingest.osm_emergencia`"
        )
    df = pd.concat(quadros, ignore_index=True)
    # Coordenada fora do RS (erro de cadastro) distorceria toda distancia.
    return df[(df.lat.between(-34, -26.5)) & (df.lon.between(-58, -49))].reset_index(drop=True)


def build() -> RecursosResult:
    pontos = _carregar_pontos()
    centroides = _centroides()

    # Distancia ao recurso mais proximo de cada papel, por municipio.
    por_papel: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for papel in PAPEIS:
        sub = pontos[pontos["papel"] == papel]
        por_papel[papel] = (sub["lon"].to_numpy(), sub["lat"].to_numpy())

    por_municipio: dict[int, dict[str, Any]] = {}
    for cod, (lon, lat) in centroides.items():
        linha: dict[str, Any] = {}
        for papel, (plons, plats) in por_papel.items():
            if plons.size == 0:
                linha[papel] = {"n_no_municipio": 0, "km_mais_proximo": None,
                                "completude": PAPEIS[papel]["completude"]}
                continue
            d = _haversine(lon, lat, plons, plats)
            # "no municipio" aproximado por proximidade ao centroide: a
            # alternativa (ponto-em-poligono para 1.700 pontos x 497 areas) nao
            # muda nenhuma decisao e custa muito mais.
            linha[papel] = {
                "n_no_municipio": int((d <= 12.0).sum()),
                "km_mais_proximo": round(float(d.min()), 1),
                "completude": PAPEIS[papel]["completude"],
            }
        por_municipio[cod] = linha

    vazios: dict[str, int] = {}
    for papel in PAPEIS_CRITICOS:
        vazios[papel] = sum(
            1 for v in por_municipio.values()
            if (v[papel]["km_mais_proximo"] or 0) >= LIMIAR_VAZIO_KM
        )

    resumo = {
        "version": VERSION,
        "total_pontos": int(len(pontos)),
        "por_papel": {
            papel: {
                **PAPEIS[papel],
                "n": int((pontos["papel"] == papel).sum()),
                "municipios_alem_do_limiar": vazios.get(papel),
            }
            for papel in PAPEIS
        },
        "limiar_vazio_km": LIMIAR_VAZIO_KM,
        "subtipos_moveis": (
            pontos[pontos["papel"] == "movel"]["subtipo"].value_counts().to_dict()
            if "subtipo" in pontos else {}
        ),
        "ressalvas": [
            "E BASE, nunca viatura: nao ha dado publico de frota de ambulancia, viatura "
            "policial ou caminhao de bombeiro.",
            "O CNES nao registra a frota do SAMU — as unidades moveis cadastradas incluem "
            "farmacia movel e unidade odontologica. As centrais de regulacao sao o sinal "
            "confiavel de cobertura SAMU; a contagem de moveis nao e.",
            "Bombeiro e policia vem do OpenStreetMap (colaborativo). Ausencia no mapa NAO "
            "prova ausencia no territorio — um vazio ali e hipotese de vazio.",
            "Distancia e linha reta sobre centroide municipal, nunca rota. E um PISO da "
            "dificuldade de acesso: em cheia a distancia real cresce e as vezes nao existe.",
        ],
    }
    return RecursosResult(
        pontos=pontos.to_dict(orient="records"),
        por_municipio=por_municipio,
        resumo=resumo,
    )


def vazios_priorizados(indice: list[dict[str, Any]], limite: int = 40) -> list[dict[str, Any]]:
    """Municipios ordenados por (risco x vazio de cobertura).

    E o mais perto de "onde realocar" que o dado sustenta: cruza o indice de
    prioridade preventiva com a distancia ao recurso critico mais proximo.
    NAO e otimizacao de frota — ver ressalvas.
    """
    rec = build()
    linhas = []
    for m in indice:
        if m["score"] is None:
            continue
        cob = rec.por_municipio.get(m["cod_mun"])
        if not cob:
            continue
        faltas = [
            {
                "papel": p,
                "label": PAPEIS[p]["label"],
                "km": cob[p]["km_mais_proximo"],
                "completude": cob[p]["completude"],
            }
            for p in PAPEIS_CRITICOS
            if (cob[p]["km_mais_proximo"] or 0) >= LIMIAR_VAZIO_KM
        ]
        if not faltas:
            continue
        pior = max(f["km"] for f in faltas)
        linhas.append({
            "cod_mun": m["cod_mun"],
            "municipio": m["municipio"],
            "score": m["score"],
            "level": m["level"],
            "populacao": m["populacao"],
            "faltas": faltas,
            "pior_km": pior,
            # Produto risco x distancia, ambos normalizados de forma grosseira.
            # Serve para ORDENAR, nao para ser lido como grandeza — por isso
            # nao aparece na interface como numero.
            "_ordem": (m["score"] / 100.0) * min(pior / 100.0, 1.0),
        })
    linhas.sort(key=lambda x: -x["_ordem"])
    for x in linhas:
        x.pop("_ordem")
    return linhas[:limite]
