"""Perigo geotecnico e fragilidade de acesso — o que a agua derruba e corta.

Por que esta camada existe separada
===================================

O indice municipal (`src/risk/municipal.py`) mede perigo HIDRICO e exclui de
proposito os perigos geotecnicos:

    PERIGOS_HIDRICOS = inundacao, enchente, alagamento, solapamento, erosao

com o comentario "Deslizamento/queda de blocos ficam fora: sao geotecnicos,
deflagrados por chuva mas com fisica, mapa de risco e obra de mitigacao
diferentes. Misturar os dois num indice de 'enchente' produz prioridade errada
para os dois publicos."

A exclusao continua certa — e deixava 5 variaveis ingeridas sem uso nenhum.
Este modulo lhes da a camada propria que a exclusao pressupunha.

O que ele mede
==============

geotecnico   deslizamento, corrida de massa, queda de blocos, queda de
             barreira e desabamento de edificacao, declarados no evento de
             26/04/2024. Sao encosta e talude, nao planicie: a mitigacao e
             contencao e realocacao, nunca dique nem drenagem.

acesso       o que corta o municipio do resto: dano viario, area ilhada,
             queda de barreira em estrada, dano a porto/aeroporto, e a
             densidade de pontes na malha principal por onde esse acesso
             passa.

barragem     dano declarado a barragem. Fica em destaque proprio por ser o
             unico perigo aqui cuja falha e catastrofica e a jusante — o
             municipio que sofre pode nao ser o que tem a obra.

O LIMITE QUE DEFINE A LEITURA DE "MANUTENCAO DE PONTES"
=======================================================

Ha 2.159 pontes mapeadas na malha principal do RS. Nao ha, para nenhuma delas,
dado publico de **estado de conservacao, ano de construcao, vao, carga ou
laudo de inspecao**. O OSM registra que existe uma ponte ali; nao diz se ela
aguenta.

Logo, "manutencao de pontoes" nesta central so pode significar ONDE
INSPECIONAR — priorizar vistoria onde muitas travessias servem um municipio
que ja declarou dano viario e ja ficou ilhado. Nunca "esta ponte precisa de
reparo". Quem tem esse dado e o DAER e o DNIT, e ele nao e publico em formato
utilizavel.

Mesma disciplina de ADR-036 (estabelecimento, nunca leito) e ADR-053 (base,
nunca viatura): aqui e existencia, nunca conservacao.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
INTERIM = REPO_ROOT / "data" / "interim"

MUNIC_PARQUET = INTERIM / "ibge_munic_rs.parquet"
OSM_PARQUET = INTERIM / "osm_emergencia.parquet"

VERSION = "geotecnico-v1"

# Perigos de encosta e talude. Os pesos separam o que mata do que interrompe:
# corrida de massa e deslizamento levam gente junto; queda de barreira corta
# estrada. Ambos importam, por motivos diferentes.
GEOTECNICO = {
    "oc_deslizamento": ("deslizamento e escorregamento", 0.30),
    "oc_corrida_massa": ("corrida de massa (lama, troncos)", 0.26),
    "oc_desabamento": ("desabamento de edificacao", 0.20),
    "oc_queda_blocos": ("queda, tombamento e rolamento de blocos", 0.14),
    "oc_queda_barreira": ("queda de barreira em estrada", 0.10),
}

# Fragilidade de acesso: o que separa o municipio do socorro.
ACESSO = {
    "dano_viario": ("danos a rodovias, pontes e ferrovias", 0.40),
    "areas_ilhadas": ("areas ilhadas", 0.35),
    "oc_queda_barreira": ("queda de barreira em estrada", 0.15),
    "dano_portos_aeroportos": ("danos a portos e aeroportos", 0.10),
}

# Raio para atribuir uma ponte ao municipio. Aproximacao por centroide, igual
# ao resto do projeto: ponto-em-poligono para 2.159 pontes x 497 areas nao
# mudaria nenhuma decisao e custaria muito mais.
RAIO_PONTE_KM = 25.0

# A partir de quantas pontes na malha principal o municipio entra na lista de
# vistoria prioritaria, quando ja tem dano viario declarado. Cinco e escolha
# editorial: abaixo disso a inspecao e caso a caso, nao programa.
MIN_PONTES_VISTORIA = 5


def _b(v: Any) -> bool | None:
    if v is None or v is pd.NA or (isinstance(v, float) and math.isnan(v)):
        return None
    return bool(v)


def _score(row: pd.Series, mapa: dict[str, tuple[str, float]]) -> tuple[float | None, list[str]]:
    """Soma ponderada das flags verdadeiras, ou None se nada foi respondido.

    None e nao 0.0 quando o municipio nao respondeu: a diferenca entre "nao
    houve deslizamento" e "nao sabemos" e a mesma que o resto do projeto
    mantem em toda parte.
    """
    total = 0.0
    ativos: list[str] = []
    respondeu = False
    for col, (rotulo, peso) in mapa.items():
        v = _b(row.get(col))
        if v is None:
            continue
        respondeu = True
        if v:
            total += peso
            ativos.append(rotulo)
    if not respondeu:
        return None, []
    return round(min(total, 1.0), 4), ativos


def _haversine(lon1: float, lat1: float, lon2: np.ndarray, lat2: np.ndarray) -> np.ndarray:
    r = 6371.0
    p1, p2 = math.radians(lat1), np.radians(lat2)
    a = (
        np.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * r * np.arcsin(np.sqrt(a))


@dataclass(frozen=True)
class GeotecnicoResult:
    rows: list[dict[str, Any]]
    resumo: dict[str, Any]


def build(centroides: dict[int, tuple[float, float]] | None = None) -> GeotecnicoResult:
    if not MUNIC_PARQUET.exists():
        raise FileNotFoundError(
            f"{MUNIC_PARQUET} ausente — rode `python -m src.ingest.ibge_rs munic`"
        )
    df = pd.read_parquet(MUNIC_PARQUET)

    if centroides is None:
        from src.risk.recursos import _centroides

        centroides = _centroides()

    pontes = pd.DataFrame()
    if OSM_PARQUET.exists():
        o = pd.read_parquet(OSM_PARQUET)
        if "papel" in o.columns:
            pontes = o[o["papel"] == "ponte"].copy()
    plon = pontes["lon"].to_numpy() if len(pontes) else np.array([])
    plat = pontes["lat"].to_numpy() if len(pontes) else np.array([])
    pvia = pontes["via"].to_numpy() if len(pontes) and "via" in pontes else np.array([])

    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        cod = int(r["cod_mun"])
        geo_score, geo_ativos = _score(r, GEOTECNICO)
        acc_score, acc_ativos = _score(r, ACESSO)

        n_pontes = 0
        n_estruturantes = 0
        if plon.size and cod in centroides:
            lon, lat = centroides[cod]
            perto = _haversine(lon, lat, plon, plat) <= RAIO_PONTE_KM
            n_pontes = int(perto.sum())
            if pvia.size:
                # Estruturante = motorway ou trunk. A queda de uma BR isola;
                # a de uma secundaria desvia.
                n_estruturantes = int(np.sum(perto & np.isin(pvia, ["motorway", "trunk"])))

        rows.append({
            "cod_mun": cod,
            "municipio": str(r["municipio"]),
            "populacao": None if pd.isna(r.get("populacao")) else int(r["populacao"]),
            "geotecnico": {
                "score": geo_score,
                "ocorrencias": geo_ativos,
                "basis": "measured" if geo_score is not None else None,
            },
            "acesso": {
                "score": acc_score,
                "ocorrencias": acc_ativos,
                "ficou_ilhado": _b(r.get("areas_ilhadas")),
                "dano_viario": _b(r.get("dano_viario")),
                "basis": "measured" if acc_score is not None else None,
            },
            "pontes": {
                "n_malha_principal": n_pontes,
                "n_estruturantes": n_estruturantes,
                "raio_km": RAIO_PONTE_KM,
                "basis": "measured" if plon.size else None,
                "nota": "existencia, NUNCA estado de conservacao — nao ha laudo publico",
            },
            "barragem": {
                "dano_declarado": _b(r.get("dano_barragens")),
                "basis": "measured" if _b(r.get("dano_barragens")) is not None else None,
                "nota": "a falha de barragem atinge a jusante: o municipio que sofre pode nao "
                        "ser o que tem a obra",
            },
        })

    com_geo = [x for x in rows if x["geotecnico"]["score"] is not None]
    resumo = {
        "version": VERSION,
        "n_municipios": len(rows),
        "geotecnico": {
            "n_com_ocorrencia": sum(1 for x in com_geo if x["geotecnico"]["ocorrencias"]),
            "por_tipo": {
                rotulo: int(df[col].sum(skipna=True)) if col in df else 0
                for col, (rotulo, _) in GEOTECNICO.items()
            },
            "nota": "encosta e talude, nao planicie: a mitigacao e contencao e realocacao, "
                    "nunca dique nem drenagem",
        },
        "acesso": {
            "n_com_dano_viario": int(df["dano_viario"].sum(skipna=True)) if "dano_viario" in df else 0,
            "n_ilhados": int(df["areas_ilhadas"].sum(skipna=True)) if "areas_ilhadas" in df else 0,
        },
        "pontes": {
            "n_total_malha_principal": int(len(pontes)),
            "por_via": pontes["via"].value_counts().to_dict() if len(pontes) else {},
        },
        "barragens": {
            "n_com_dano": int(df["dano_barragens"].sum(skipna=True)) if "dano_barragens" in df else 0,
        },
        "limites": [
            "Perigo geotecnico e retrato do evento de 26/04/2024, nao mapa de suscetibilidade. "
            "Encosta sem ocorrencia em 2024 pode ser instavel do mesmo jeito.",
            "NAO ha dado publico de estado de conservacao, vao, carga ou laudo de inspecao de "
            "ponte. O OSM diz que existe travessia ali, nao se ela aguenta.",
            "'Manutencao de pontes' aqui significa ONDE INSPECIONAR, nunca 'esta ponte precisa "
            "de reparo'. Quem tem esse dado e o DAER e o DNIT, e nao e publico.",
            "Pontes atribuidas por proximidade ao centroide, nao por ponto-em-poligono.",
            "Cadastro de barragens (SNISB/ANA) nao esta ingerido: aqui ha apenas DANO declarado "
            "no evento, nao inventario nem categoria de risco.",
        ],
    }
    return GeotecnicoResult(rows=rows, resumo=resumo)


def vistoria_prioritaria(indice: list[dict[str, Any]], limite: int = 30) -> list[dict[str, Any]]:
    """Municipios onde a vistoria de travessia rende mais.

    Criterio: ja declarou dano viario OU ficou ilhado em 2024, E tem pelo
    menos MIN_PONTES_VISTORIA travessias na malha principal. Ordena por risco.

    Nao e lista de pontes com problema — e lista de onde procurar. A diferenca
    importa: sem laudo publico, apontar uma ponte especifica seria invencao.
    """
    g = build()
    por_cod = {r["cod_mun"]: r for r in g.rows}
    saida = []
    for m in indice:
        if m["score"] is None:
            continue
        r = por_cod.get(m["cod_mun"])
        if not r:
            continue
        gatilho = r["acesso"]["dano_viario"] is True or r["acesso"]["ficou_ilhado"] is True
        if not gatilho or r["pontes"]["n_malha_principal"] < MIN_PONTES_VISTORIA:
            continue
        motivos = []
        if r["acesso"]["dano_viario"]:
            motivos.append("danos a rodovias, pontes ou ferrovias em 2024")
        if r["acesso"]["ficou_ilhado"]:
            motivos.append("areas ilhadas em 2024")
        saida.append({
            "cod_mun": m["cod_mun"],
            "municipio": m["municipio"],
            "score": m["score"],
            "level": m["level"],
            "n_pontes": r["pontes"]["n_malha_principal"],
            "n_estruturantes": r["pontes"]["n_estruturantes"],
            "motivos": motivos,
            "geotecnico": r["geotecnico"]["ocorrencias"],
        })
    saida.sort(key=lambda x: (-(x["score"] or 0), -x["n_pontes"]))
    return saida[:limite]
