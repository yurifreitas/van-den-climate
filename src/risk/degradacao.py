"""Degradacao do solo — o risco que chega antes da cheia, e fica depois dela.

POR QUE ESTA CAMADA EXISTE
==========================

A cheia e um evento; a degradacao e uma condicao. As duas se alimentam, e a
central so enxergava a primeira.

Solo degradado infiltra menos, entao a mesma chuva escoa mais — a camada
hidrologica ja mede esse lado. O lado que falta e o inverso e mais lento: a
enxurrada leva o horizonte superficial embora, e o que sobra infiltra menos
ainda no ano seguinte. Em encosta de basalto raso, como a do Vale do Taquari,
poucos centimetros de perda separam solo agricola de saprolito exposto, e essa
travessia e irreversivel em escala humana.

Uma central que so conta enchente mede o ano; medir o solo mede a decada.

O QUE E CALCULADO, E COM QUE HONESTIDADE
========================================

A estrutura e a da Equacao Universal de Perda de Solo revisada (RUSLE):

    A = R * K * LS * C * P

    R   erosividade da chuva      — da serie do GHCN
    K   erodibilidade do solo     — da ordem e textura do IBGE
    LS  relevo (comprimento/declive) — da classe de relevo do IBGE
    C   cobertura e manejo        — do uso da terra do IBGE
    P   praticas conservacionistas — assumido 1

Cada fator aqui e um VALOR DE TABELA atribuido a uma classe cartografica, nao
uma medida de campo. K vem de literatura por ordem de solo, nao de ensaio de
erodibilidade; LS vem de uma classe qualitativa de relevo ("ondulado"), nao de
modelo digital de elevacao; C vem do uso mapeado a 1:250.000, nao da cobertura
do talhao.

Consequencia direta, e ela e severa: **o valor absoluto em t/ha/ano nao deve
ser usado como quantidade**. Ele e publicado porque a ordem de grandeza
comunica (0,5 e 40 sao mundos diferentes), mas a leitura valida e ORDINAL —
entre dois municipios do RS, qual perde mais solo por hectare. Por isso o
payload traz o percentil junto do numero, e por isso `P = 1`: fingir conhecer
terraceamento e plantio direto por municipio seria inventar a unica variavel
que o produtor de fato controla.

O QUE NAO ESTA AQUI
===================

Erosao LINEAR — sulco, ravina e vocoroca — nao e o que a RUSLE calcula. Ela
estima perda laminar e em sulcos rasos. Vocoroca ativa e o processo que mais
assusta e mais destroi estrada rural no RS, e ela nao aparece neste numero.

Movimento de MASSA (deslizamento) tambem nao: e outra fisica, governada por
poro-pressao e resistencia ao cisalhamento, e ja tem camada propria em
`src/risk/geotecnico.py`.

E nao ha serie temporal. Isto e um retrato do potencial sob as condicoes
mapeadas, nao uma medida de quanto solo ja se perdeu. Para o segundo seriam
necessarios levantamentos repetidos que nao existem em base publica para o
estado.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.risk.hidrologia import (
    GHCN_DIARIO,
    GHCN_ESTACOES,
    _km,
    _sem_acento,
    classe_cobertura,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
INTERIM = REPO_ROOT / "data" / "interim"

CRUZADO_PARQUET = INTERIM / "bdia_cruzado_rs.parquet"
PEDOLOGIA_PARQUET = INTERIM / "bdia_pedologia_rs.parquet"
VEGETACAO_PARQUET = INTERIM / "bdia_vegetacao_rs.parquet"

VERSION = "degradacao-v1"

# ---------------------------------------------------------------------------
# K — erodibilidade por ordem de solo, em t.ha.h/(ha.MJ.mm)
# ---------------------------------------------------------------------------
# Faixas tipicas da literatura brasileira de conservacao de solo. O que a
# tabela captura, e que a intuicao inverte: o Latossolo argiloso e dos MENOS
# erodiveis do estado, porque a estrutura granular resiste a desagregacao,
# enquanto o Argissolo de horizonte B textural e dos mais, porque a agua
# encontra a barreira do B e escoa por dentro do A arenoso, levando-o.
#
# Sao valores centrais de faixa, nao medidas. Duas amostras da mesma ordem
# variam por um fator de dois; usar isto para dimensionar terraco seria abuso.
K_POR_ORDEM: dict[str, float] = {
    "LATOSSOLO": 0.015,
    "NITOSSOLO": 0.020,
    "ARGISSOLO": 0.045,
    "PLANOSSOLO": 0.035,
    "CAMBISSOLO": 0.045,
    "CHERNOSSOLO": 0.030,
    "LUVISSOLO": 0.045,
    "NEOSSOLO": 0.050,
    "GLEISSOLO": 0.025,
    "ORGANOSSOLO": 0.010,
    "PLINTOSSOLO": 0.035,
    "VERTISSOLO": 0.030,
    "ESPODOSSOLO": 0.030,
    "DUNAS": 0.010,
    "AFLORAMENTOS DE ROCHAS": 0.001,
}
K_PADRAO = 0.035

# Textura desloca K dentro da ordem: areia solta desagrega facil mas infiltra,
# argila pesada resiste. O ajuste e pequeno de proposito — a ordem ja carrega
# a maior parte da informacao, e empilhar dois ajustes fracos sobre um valor
# de tabela produz falsa resolucao.
AJUSTE_TEXTURA: tuple[tuple[str, float], ...] = (
    ("MUITO ARGILOSA", 0.75),
    ("ARENOSA/", 1.20),
    ("ARENOSA", 1.15),
    ("ARGILOSA", 0.85),
    ("CASCALHENTA", 0.90),
)

# ---------------------------------------------------------------------------
# LS — relevo
# ---------------------------------------------------------------------------
# A classe de relevo do IBGE e uma faixa de declividade (plano < 3%, suave
# ondulado 3-8%, ondulado 8-20%, forte ondulado 20-45%, montanhoso 45-75%).
# Os LS abaixo sao os valores da equacao para o ponto medio de cada faixa a um
# comprimento de rampa de 50 m — comprimento assumido, porque nao ha modelo de
# elevacao ingerido.
#
# LS cresce mais que linearmente com a declividade: do plano ao montanhoso ha
# um fator de quarenta. E por isso que a classe de relevo, sozinha, domina o
# resultado — e por isso que trocar a classe qualitativa por declividade real
# (Copernicus DEM 30 m, ja mapeado como fonte) e a melhoria de maior retorno
# desta camada inteira.
LS_POR_RELEVO: dict[str, float] = {
    "plano": 0.15,
    "plano e suave ondulado": 0.30,
    "suave ondulado e plano": 0.35,
    "suave ondulado": 0.55,
    "suave ondulado e ondulado": 1.10,
    "ondulado e suave ondulado": 1.30,
    "ondulado": 2.10,
    "ondulado e forte ondulado": 3.40,
    "forte ondulado e ondulado": 4.00,
    "forte ondulado": 5.50,
    "forte ondulado e montanhoso": 7.00,
    "montanhoso e forte ondulado": 7.50,
    "montanhoso": 9.00,
    "montanhoso e escarpado": 11.00,
}
LS_PADRAO = 1.0

# ---------------------------------------------------------------------------
# C — cobertura e manejo
# ---------------------------------------------------------------------------
# Reaproveita a classificacao de cobertura da camada hidrologica de proposito:
# se a lavoura tem um CN ali e um C aqui, os dois numeros descrevem o mesmo
# pedaco de chao, e uma mudanca de criterio precisa mover os dois juntos.
C_POR_COBERTURA: dict[str, float] = {
    "agua": 0.0,
    "banhado": 0.003,
    "floresta_nativa": 0.001,
    "vegetacao_secundaria": 0.010,
    "campo_nativo": 0.010,
    "silvicultura": 0.030,
    "pastagem": 0.050,
    "agropecuaria": 0.150,
    "agricultura": 0.250,
    "urbano": 0.020,
    "dunas": 0.100,
}

# A classe e por POSICAO NO ESTADO, nao por corte absoluto — e a decisao mais
# importante deste modulo.
#
# A RUSLE nao tem teto: LS cresce sem limite com a declividade, e num municipio
# de encosta de basalto o produto devolve centenas de toneladas por hectare ao
# ano. Fisicamente aquilo nao acontece — o perfil ali tem poucos decimetros e
# se esgotaria em poucos anos — mas a equacao nao sabe disso, e P=1 remove a
# unica defesa que existe no campo. O numero absoluto e, portanto, um POTENCIAL
# sob hipoteses pessimistas, nao uma taxa observavel.
#
# Cortar em "50 t/ha/ano = alta" importaria da literatura um limiar que so vale
# para valores calibrados, e carimbaria metade do estado de vermelho. O que o
# dado sustenta e a ordem: onde, no RS, o mesmo metodo devolve mais. Entao a
# classe e quintil, e o rotulo diz "no estado".
CLASSES_PERCENTIL = (
    (0.90, "entre os 10% maiores do RS"),
    (0.75, "quarto superior do RS"),
    (0.50, "acima da mediana do RS"),
    (0.25, "abaixo da mediana do RS"),
    (0.00, "quarto inferior do RS"),
)

# Relevo a partir do qual uso intensivo vira problema conservacionista, e nao
# apenas lavoura em terreno inclinado: 'ondulado' e a faixa 8-20%, onde a
# legislacao e a pratica ja exigem terraceamento.
RELEVOS_DECLIVOSOS = {
    "ondulado", "ondulado e forte ondulado", "forte ondulado e ondulado",
    "forte ondulado", "forte ondulado e montanhoso", "montanhoso e forte ondulado",
    "montanhoso", "montanhoso e escarpado", "ondulado e suave ondulado",
}
USOS_INTENSIVOS = {"agricultura", "agropecuaria"}


def fator_k(ordem: str | None, textura: str | None) -> float:
    base = K_POR_ORDEM.get(_sem_acento(ordem or ""), K_PADRAO)
    tex = _sem_acento(textura or "")
    for marca, mult in AJUSTE_TEXTURA:
        if marca in tex:
            return round(base * mult, 4)
    return base


def fator_ls(relevo: str | None) -> float:
    return LS_POR_RELEVO.get(" ".join(str(relevo or "").split()).lower(), LS_PADRAO)


def erosividade_r(precipitacao_anual_mm: float) -> float:
    """R anual (MJ.mm/(ha.h.ano)) a partir da chuva anual.

    Relacao de Renard e Freimund (1994), que estima R a partir do total anual
    quando nao ha serie de intensidade — e nao ha: o GHCN traz totais diarios,
    e erosividade se define sobre a intensidade em 30 minutos.

    Essa e a maior aproximacao desta camada, e ela e otimista de um jeito
    especifico: dois lugares com a mesma chuva anual, um deles concentrando-a
    em poucas tempestades, recebem o mesmo R aqui, quando o segundo erode
    muito mais. No RS isso subestima o oeste, de chuva convectiva concentrada.
    """
    p = max(precipitacao_anual_mm, 1.0)
    if p < 850.0:
        return 0.0483 * p**1.610
    return 587.8 - 1.219 * p + 0.004105 * p**2


@dataclass(frozen=True)
class DegradacaoResult:
    rows: list[dict[str, Any]]
    resumo: dict[str, Any]
    limites: list[str]


def _precipitacao_anual_por_estacao(min_anos: int = 20) -> dict[str, float]:
    """Chuva anual media por estacao, sobre anos com cobertura suficiente.

    Ano com menos de 300 dias observados e descartado inteiro: somar o que ha
    e chamar de total anual produziria uma serie que cai quando a estacao
    falha, e a queda entraria no modelo como se fosse seca.
    """
    d = pd.read_parquet(GHCN_DIARIO)
    d["ano"] = pd.to_datetime(d["data"]).dt.year
    g = d.groupby(["station_id", "ano"]).prcp_mm.agg(["sum", "count"]).reset_index()
    g = g[g["count"] >= 300]
    med = g.groupby("station_id")["sum"].agg(["mean", "size"])
    med = med[med["size"] >= min_anos]
    return {str(i): float(r["mean"]) for i, r in med.iterrows()}


def build(centroides: dict[int, tuple[float, float]] | None = None) -> DegradacaoResult:
    if not CRUZADO_PARQUET.exists():
        raise FileNotFoundError(
            f"{CRUZADO_PARQUET} ausente — rode `python -m src.ingest.ibge_bdia`"
        )
    cruzado = pd.read_parquet(CRUZADO_PARQUET)
    chuva_anual = _precipitacao_anual_por_estacao()
    estacoes = pd.read_parquet(GHCN_ESTACOES)
    estacoes = estacoes[estacoes.station_id.isin(chuva_anual)]

    if centroides is None:
        from src.risk.recursos import _centroides

        centroides = _centroides()

    linhas: list[dict[str, Any]] = []
    for cod, g in cruzado.groupby("cod_mun"):
        cod = int(cod)
        area = float(g.km2.sum())
        if area <= 0:
            continue

        r_local, estacao = None, None
        if cod in centroides and len(estacoes):
            lon, lat = centroides[cod]
            d = estacoes.assign(
                km=[_km(lat, lon, e.lat, e.lon) for e in estacoes.itertuples()]
            ).nsmallest(1, "km").iloc[0]
            estacao = {"station_id": str(d.station_id), "nome": d.nome,
                       "km": round(float(d.km), 1),
                       "chuva_anual_mm": round(chuva_anual[str(d.station_id)])}
            r_local = erosividade_r(chuva_anual[str(d.station_id)])

        perda_num = 0.0
        area_valida = 0.0
        km2_intensivo_declive = 0.0
        km2_solo_raso_sob_uso = 0.0
        km2_permanente_em_declive = 0.0
        pior: list[dict[str, Any]] = []
        for row in g.itertuples():
            cob = classe_cobertura(row.vege_legenda_2, row.vege_nm_uantr)
            if cob == "agua":
                continue
            relevo = " ".join(str(row.pedo_relevo or "").split()).lower()
            declivoso = relevo in RELEVOS_DECLIVOSOS
            raso = "LITOLICO" in _sem_acento(row.pedo_legenda_2 or "")
            if declivoso and cob in USOS_INTENSIVOS:
                km2_intensivo_declive += row.km2
            if declivoso and cob not in USOS_INTENSIVOS and cob != "urbano":
                km2_permanente_em_declive += row.km2
            if raso and cob in USOS_INTENSIVOS:
                km2_solo_raso_sob_uso += row.km2

            k = fator_k(row.pedo_ordem, row.pedo_textura)
            ls = fator_ls(row.pedo_relevo)
            c = C_POR_COBERTURA.get(cob, 0.15)
            if r_local is None:
                continue
            a = r_local * k * ls * c
            perda_num += a * row.km2
            area_valida += row.km2
            pior.append({
                "solo": row.pedo_ordem or row.pedo_legenda_2,
                "relevo": row.pedo_relevo,
                "cobertura": cob,
                "km2": round(row.km2, 1),
                "indice_t_ha_ano": round(a, 1),
            })

        if area_valida <= 0:
            continue
        perda = perda_num / area_valida
        pior.sort(key=lambda d: -(d["indice_t_ha_ano"] * d["km2"]))

        linhas.append({
            "cod_mun": cod,
            "municipio": g.municipio.iloc[0],
            "area_km2": round(area, 1),
            # Nome longo de proposito: quem ler `perda_t_ha_ano` vai acreditar
            # que sao toneladas perdidas. Nao sao — e o indice da equacao sob
            # P=1, e o proprio nome do campo carrega isso.
            "indice_rusle_t_ha_ano": round(perda, 1),
            # Os tres numeros abaixo NAO passam por tabela nenhuma: sao area
            # medida cruzando duas classes do IBGE. Quando o indice for
            # contestado — e ele deve ser —, estes continuam de pe.
            "km2_uso_intensivo_em_declive": round(km2_intensivo_declive, 1),
            "frac_uso_intensivo_em_declive": round(km2_intensivo_declive / area, 4),
            "km2_solo_raso_sob_uso_intensivo": round(km2_solo_raso_sob_uso, 1),
            "km2_cobertura_permanente_em_declive": round(km2_permanente_em_declive, 1),
            "erosividade_r": None if r_local is None else round(r_local),
            "estacao_chuva": estacao,
            "onde_mais_perde": pior[:5],
        })

    valores = np.array([r["indice_rusle_t_ha_ano"] for r in linhas]) if linhas else np.array([])
    for r in linhas:
        p = float((valores <= r["indice_rusle_t_ha_ano"]).mean())
        r["percentil_rs"] = round(p, 3)
        r["classe"] = next(lbl for corte, lbl in CLASSES_PERCENTIL if p >= corte)
    rows = sorted(linhas, key=lambda r: -r["indice_rusle_t_ha_ano"])

    resumo = {
        "version": VERSION,
        "n_municipios": len(rows),
        "indice_mediano_t_ha_ano": round(float(np.median(valores)), 1) if linhas else None,
        "p_assumido": 1.0,
        "comprimento_rampa_assumido_m": 50,
        "km2_uso_intensivo_em_declive_rs": round(
            sum(r["km2_uso_intensivo_em_declive"] for r in rows), 1
        ),
        "km2_solo_raso_sob_uso_intensivo_rs": round(
            sum(r["km2_solo_raso_sob_uso_intensivo"] for r in rows), 1
        ),
        "nota_escala": (
            "O indice e da equacao sob P=1 e sem teto: em encosta declivosa ele "
            "devolve centenas de t/ha/ano, valor que o proprio perfil raso torna "
            "impossivel de sustentar. Leia a POSICAO no estado, nunca a "
            "quantidade."
        ),
    }
    limites = [
        "O indice nao e taxa de perda observavel: a RUSLE nao tem teto em "
        "declividade e P=1 remove a pratica conservacionista. Em encosta o "
        "resultado excede o que o perfil raso poderia sustentar. A classe "
        "publicada e a POSICAO no estado, nunca um corte absoluto importado.",
        "Todo fator e valor de tabela atribuido a classe cartografica, nao "
        "medida de campo: K por ordem de solo (nao por ensaio), LS por classe "
        "qualitativa de relevo (nao por modelo de elevacao), C por uso "
        "mapeado a 1:250.000 (nao por talhao).",
        "O valor em t/ha/ano vale como ORDEM DE GRANDEZA e para ordenar "
        "municipios. Nao e quantidade de solo perdido e nao dimensiona obra.",
        "P=1: nenhuma pratica conservacionista e considerada. Terraceamento e "
        "plantio direto reduzem perda de forma substancial e sao justamente a "
        "variavel que o produtor controla — supor um valor por municipio seria "
        "inventar o unico numero que importa para a decisao.",
        "R vem do total anual (Renard e Freimund), nao da intensidade em 30 "
        "minutos. Isso subestima onde a chuva se concentra em poucas "
        "tempestades, que no RS e o oeste.",
        "A RUSLE estima erosao LAMINAR e em sulcos rasos. Vocoroca — o processo "
        "que mais destroi estrada rural no estado — nao aparece aqui, e "
        "deslizamento e outra fisica, com camada propria no geotecnico.",
        "E um retrato do potencial sob as condicoes mapeadas, nao uma medida do "
        "solo ja perdido. Nao ha serie temporal.",
    ]
    return DegradacaoResult(rows=rows, resumo=resumo, limites=limites)
