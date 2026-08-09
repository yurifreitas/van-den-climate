"""Condicao de umidade antecedente — qual dos dois numeros vale HOJE.

O QUE ESTA CAMADA RESOLVE
=========================

`src/risk/hidrologia.py` publica dois Curve Numbers por municipio: o de solo
seco e o de solo encharcado. A diferenca entre eles nao e pequena — um CN de
74 vira 87, e a mesma chuva de 100 mm escoa 45 mm ou 68 mm. Ate aqui a central
mostrava os dois e deixava a escolha para quem lesse, o que na pratica
significa que ninguem escolhia.

Com a chuva diaria do CPC (`src/ingest/cpc_precip.py`) a escolha deixa de ser
retorica: a condicao de umidade e determinada pela chuva dos CINCO DIAS
anteriores, e essa chuva agora e medida ate ontem.

A REGRA, E DE ONDE ELA VEM
==========================

E a tabela classica do metodo (SCS/NRCS), com os limiares em milimetros:

                        estacao dormente     estacao de crescimento
    AMC I  (seco)            < 12,7 mm              < 35,6 mm
    AMC II (media)        12,7 a 27,9 mm         35,6 a 53,3 mm
    AMC III (umido)          > 27,9 mm              > 53,3 mm

E as conversoes de CN:

    CN1 = 4,2 CN2 / (10 - 0,058 CN2)
    CN3 = 23 CN2 / (10 + 0,13 CN2)

DUAS ESCOLHAS QUE PRECISAM APARECER
===================================

1. **Estacao de crescimento no RS = outubro a abril.** A tabela original e do
   hemisferio norte e fala em "growing season" sem definir data, porque quem a
   usava sabia. Aqui a definicao e nossa, viaja no payload, e desloca o limiar
   em quase 26 mm — o suficiente para trocar a classe num dia de chuva media.

2. **A chuva vem de celula de 55 km.** Municipios vizinhos compartilham
   celula e portanto compartilham condicao. Isso e menos grave aqui do que
   pareceria: umidade antecedente e um fenomeno de escala regional, ao
   contrario da tempestade que causa o alagamento. Mas continua sendo o
   limite dominante, e todo numero daqui carrega quantos municipios dividem a
   celula.

O QUE ISTO NAO E
================

Nao e previsao. A condicao publicada e a de ONTEM, apurada com chuva
observada. Se chover hoje a noite, ela muda amanha — e a central nao tem como
antecipar isso, por decisao de escopo (ADR-013).

E nao e umidade do solo medida. Umidade de verdade se mede com sonda ou
satelite de micro-ondas; isto e um proxy por chuva acumulada, que ignora
evapotranspiracao, textura e lencol. Dois municipios com a mesma chuva de
cinco dias podem estar em estados bem diferentes se um for arenoso e o outro
argiloso — e a tabela nao sabe disso.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
INTERIM = REPO_ROOT / "data" / "interim"

CPC_PARQUET = INTERIM / "cpc_precip_rs.parquet"

VERSION = "antecedente-v1"

# Limiares de chuva acumulada em 5 dias (mm). Ver o cabecalho.
LIMIARES = {
    "dormente": (12.7, 27.9),
    "crescimento": (35.6, 53.3),
}

# Estacao de crescimento no RS. Definicao nossa — a tabela original nao data.
MESES_CRESCIMENTO = {10, 11, 12, 1, 2, 3, 4}

DIAS_ANTECEDENTES = 5

# Chuva a partir da qual o dia conta como "dia com chuva". 1 mm e o corte
# padrao dos indices ETCCDI, o mesmo ja usado no alvo `wetday_freq` — manter
# o mesmo corte em toda a central evita duas definicoes de "choveu".
LIMIAR_DIA_CHUVOSO = 1.0


def cn_umidade_baixa(cn2: float) -> float:
    """CN em condicao seca (AMC I)."""
    return 4.2 * cn2 / (10.0 - 0.058 * cn2)


def cn_umidade_alta(cn2: float) -> float:
    """CN em condicao umida (AMC III)."""
    return 23.0 * cn2 / (10.0 + 0.13 * cn2)


def classe_amc(chuva_5d_mm: float, quando: date) -> tuple[str, str]:
    """(classe, estacao) para a chuva antecedente de cinco dias."""
    estacao = "crescimento" if quando.month in MESES_CRESCIMENTO else "dormente"
    baixo, alto = LIMIARES[estacao]
    if chuva_5d_mm < baixo:
        return "I", estacao
    if chuva_5d_mm > alto:
        return "III", estacao
    return "II", estacao


@dataclass(frozen=True)
class AntecedenteResult:
    rows: list[dict[str, Any]]
    resumo: dict[str, Any]
    limites: list[str]


def build(cn_por_municipio: dict[int, float] | None = None) -> AntecedenteResult:
    """Estado de umidade por municipio, e o CN que vale hoje.

    `cn_por_municipio` entra por parametro para que esta camada nao precise
    reconstruir a hidrologia inteira quando quem chama ja a tem em maos — o
    dossie e a rota /terreno montam as duas juntas.
    """
    if not CPC_PARQUET.exists():
        raise FileNotFoundError(
            f"{CPC_PARQUET} ausente — rode `python -m src.ingest.cpc_precip`"
        )
    chuva = pd.read_parquet(CPC_PARQUET)
    chuva["data"] = pd.to_datetime(chuva["data"]).dt.date
    ultimo = max(chuva["data"])

    if cn_por_municipio is None:
        from src.risk import hidrologia

        cn_por_municipio = {r["cod_mun"]: r["cn2"] for r in hidrologia.build().rows}

    linhas: list[dict[str, Any]] = []
    for cod, g in chuva.groupby("cod_mun"):
        g = g.sort_values("data")
        serie = g.set_index("data")["prcp_mm"]

        def janela(dias: int) -> float:
            corte = ultimo - pd.Timedelta(days=dias - 1).to_pytimedelta()
            return float(serie[[d >= corte for d in serie.index]].sum())

        chuva_5d = janela(DIAS_ANTECEDENTES)
        classe, estacao = classe_amc(chuva_5d, ultimo)

        # Dias desde a ultima chuva: conta para tras a partir do ultimo dia.
        # `None` quando nao choveu em toda a janela guardada — dizer "400 dias
        # sem chuva" seria afirmar uma seca que o recorte nao sustenta.
        secos = 0
        desde = None
        for d in reversed(serie.index):
            if serie[d] >= LIMIAR_DIA_CHUVOSO:
                desde = secos
                break
            secos += 1

        cn2 = cn_por_municipio.get(int(cod))
        cn_vigente = None
        if cn2 is not None:
            cn_vigente = {
                "I": cn_umidade_baixa(cn2),
                "II": cn2,
                "III": cn_umidade_alta(cn2),
            }[classe]

        linhas.append({
            "cod_mun": int(cod),
            "municipio": g.municipio.iloc[0],
            "ate": str(ultimo),
            "chuva_5d_mm": round(chuva_5d, 1),
            "chuva_30d_mm": round(janela(30), 1),
            "chuva_90d_mm": round(janela(90), 1),
            "dias_desde_chuva": desde,
            "amc": classe,
            "estacao": estacao,
            "limiar_amc_iii_mm": LIMIARES[estacao][1],
            "cn2": cn2,
            "cn_vigente": None if cn_vigente is None else round(cn_vigente, 1),
            # Quanto o estado atual desloca o escoamento em relacao a condicao
            # media. E o numero que responde "importa saber disso?" — e a
            # resposta costuma ser sim, com folga.
            "delta_cn": None if cn2 is None else round(cn_vigente - cn2, 1),
        })

    rows = sorted(linhas, key=lambda r: -r["chuva_5d_mm"])
    por_classe = pd.Series([r["amc"] for r in rows]).value_counts().to_dict()
    resumo = {
        "version": VERSION,
        "ate": str(ultimo),
        "n_municipios": len(rows),
        "dias_antecedentes": DIAS_ANTECEDENTES,
        "meses_crescimento": sorted(MESES_CRESCIMENTO),
        "estacao_vigente": rows[0]["estacao"] if rows else None,
        "por_classe": {k: int(v) for k, v in por_classe.items()},
        "chuva_5d_mediana_mm": round(float(np.median([r["chuva_5d_mm"] for r in rows])), 1) if rows else None,
        "chuva_30d_mediana_mm": round(float(np.median([r["chuva_30d_mm"] for r in rows])), 1) if rows else None,
    }
    limites = [
        "A condicao publicada e a de ONTEM, com chuva observada. Nao e previsao: "
        "se chover hoje a noite, ela muda amanha.",
        "Nao e umidade de solo medida. E proxy por chuva acumulada, que ignora "
        "evapotranspiracao, textura e lencol — dois municipios com a mesma chuva de "
        "cinco dias podem estar em estados diferentes, e a tabela nao sabe disso.",
        "A chuva vem de celula de 0,5 grau (~55 km): municipios vizinhos compartilham "
        "celula e portanto compartilham condicao. Umidade antecedente e regional, entao "
        "o custo aqui e menor que na chuva do evento — mas continua sendo o limite "
        "dominante.",
        "A estacao de crescimento (outubro a abril) e definicao NOSSA: a tabela "
        "original nao data a estacao, e a escolha desloca o limiar em quase 26 mm.",
    ]
    return AntecedenteResult(rows=rows, resumo=resumo, limites=limites)
