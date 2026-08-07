"""Risco integrado municipal — 497 municipios do RS.

O QUE ESTE MODULO E, E O QUE ELE NAO E
======================================

NAO e previsao de evento. A ADR-013 fecha essa porta e ela continua fechada:
"Maio/2024 no RS foi bloqueio sinotico. Nenhuma versao desta engine o teria
previsto." Nada aqui diz onde vai encher na semana que vem.

E um indice de PRIORIDADE PREVENTIVA: onde a proxima tempestade encontra a
pior combinacao de (a) historico de impacto hidrico observado, (b) deficit
declarado de prevencao e (c) exposicao humana — modulada pelo estado sazonal
corrente. A pergunta que responde nao e "onde vai encher", e "se eu tenho
orcamento para agir em 30 municipios antes da primavera, quais 30".

Essa distincao nao e retorica. Um indice de prioridade e falsificavel com o
dado que existe hoje; uma previsao municipal de cheia nao e — exigiria modelo
hidrodinamico por bacia, cota de rio em tempo real e chuva prevista em malha
fina, nenhum dos quais esta nesta engine.

OS QUATRO COMPONENTES
=====================

Cada componente e normalizado em [0,1], carrega proveniencia PROPRIA e pode
ser ausente (None) sem contaminar os outros — DESIGN.md §5: ausente e "—",
nunca 0.

I — Impacto hidrico observado (basis: measured)
    IBGE MUNIC 2024, suplemento "Evento Climatico RS". Quais perigos hidricos
    de fato ocorreram no evento de 26/04/2024 e qual a severidade dos danos.
    E declaracao da propria prefeitura ao IBGE: medido, nao inferido.
    Municipio que respondeu "nao fui atingido" tem I = 0.0 MEDIDO (ausencia
    observada), diferente de municipio que nao respondeu, que tem I = None.

D — Deficit de prevencao (basis: measured)
    A pergunta que o dono do projeto colocou e que nenhum painel de clima
    responde: onde a prevencao falhou por falta de manutencao, plano ou
    treinamento. O MUNIC 2024 pergunta exatamente isso — existencia de plano
    de contingencia, se foi executado, e quando nao foi, POR QUE (recurso
    financeiro, humano, material, sistema de alerta, treinamento) — alem de
    emissao de alerta e alcance do alerta na populacao.
    ATENCAO ao que D nao cobre: manutencao de ativos fisicos (casas de bomba,
    diques, comportas, bueiros). Nao existe base publica municipal disso no
    RS. Ver LIMITES abaixo — a ausencia e declarada, nao preenchida.

E — Exposicao (basis: measured)
    Populacao residente (IBGE 2024) em escala log-percentil, mais presenca
    declarada de grupos em maior risco (favelas e comunidades urbanas,
    populacao em situacao de rua, comunidades tradicionais, pessoas com
    deficiencia).

H — Perigo sazonal corrente (basis: modeled)
    O unico componente PROSPECTIVO, e o mais fraco: vem do ONI via a mesma
    heuristica de `api/routers/risk.py`, que nunca passou a ADR-007.
    Consequencia que precisa estar visivel na interface: H e ESTADUAL e
    UNIFORME. Ele desloca o nivel de todos os municipios junto e NUNCA muda a
    ordem do ranking. Quem quiser resolucao municipal de perigo precisa de uma
    camada que esta engine nao tem.

COMPOSICAO
==========

    base = 0.38*I + 0.34*D + 0.28*E          (pesos fixos, ver justificativa)
    R    = 100 * base * (0.62 + 0.38*H)

Pesos: I pesa mais porque e o unico componente que ja observou a resposta real
do territorio a uma tempestade extrema — dado de impacto vale mais que proxy.
D vem logo atras porque e o unico componente ACIONAVEL: exposicao e historico
nao se mudam por decreto, plano de contingencia e treinamento sim. E entra por
ultimo porque populacao sozinha e um proxy grosseiro (correlaciona com risco
via urbanizacao, mas tambem com capacidade de resposta).

O multiplicador nunca zera o risco (piso 0.62): mesmo em ONI neutro um
municipio com historico de inundacao e sem plano de contingencia continua
sendo prioridade preventiva. Um indice que cai a zero fora da estacao ensina
o gestor a desligar a atencao — o oposto do objetivo.

Os pesos sao uma ESCOLHA EDITORIAL declarada, nao um ajuste. Nada aqui foi
calibrado contra desfecho, porque calibrar exigiria um alvo ("catastrofe
evitada") que nao se observa. Por isso o basis do indice composto e `modeled`
e o payload carrega os pesos para que qualquer um refaca a conta com os seus.

LIMITES (vao no payload, nao so aqui)
=====================================
1. Retrato de UM evento (26/04/2024). Municipio poupado em 2024 por sorte de
   trajetoria aparece com I baixo.
2. Auto-declaracao municipal: ha incentivo assimetrico para relatar dano
   (acesso a repasse) e para nao relatar falha de prevencao.
3. Sem manutencao de ativo fisico: casas de bomba, diques e comportas — o modo
   de falha central em Porto Alegre em 2024 — nao tem base publica municipal.
   O componente existe no contrato com basis=None e valor None.
4. Sem resolucao intramunicipal: o poligono inteiro recebe um valor. Nao ha
   "ponto de enchente" por bairro nesta base.
5. H e estadual e uniforme: nunca reordena o ranking.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
INTERIM = REPO_ROOT / "data" / "interim"

MUNIC_PARQUET = INTERIM / "ibge_munic_rs.parquet"
POP_PARQUET = INTERIM / "ibge_pop_rs.parquet"
MALHA_GEOJSON = INTERIM / "ibge_malha_rs.geojson"

MODEL_VERSION = "municipal-v1"

PESOS = {"impacto": 0.38, "deficit": 0.34, "exposicao": 0.28}
PISO_SAZONAL = 0.62  # o multiplicador varia em [0.62, 1.00]

# Cortes FIXOS no indice, nao quantis. Quantil garantiria "10% criticos"
# independentemente da realidade — o indice viraria um ranking disfarcado de
# diagnostico. Com corte fixo, um ano em que tudo melhora aparece como tudo
# melhorando, que e o comportamento que um instrumento precisa ter.
CORTES = [(55.0, "high"), (42.0, "elevated"), (28.0, "moderate")]
NIVEL_PADRAO = "low"

# Cobertura minima de peso para o indice ser publicavel.
#
# Escrito depois de o modelo colocar Bage em 1o lugar com 90 pontos: o
# municipio nao respondeu ao suplemento do MUNIC, sobrou so exposicao (peso
# 0.28), a renormalizacao esticou esse unico componente para a escala inteira
# e a ausencia de dado virou risco alto. Numa lista de prioridade preventiva
# esse e o pior erro possivel — pior que subestimar, porque desloca orcamento
# para onde nao ha evidencia e o faz com aparencia de certeza.
#
# Duas travas, nao uma:
#   1. peso coberto >= 0.60 — exposicao sozinha (0.28) nunca produz indice;
#   2. impacto OU deficit presente — sao os dois componentes que carregam
#      sinal de risco. Populacao alta sem nenhuma evidencia de perigo nem de
#      falha de prevencao nao e prioridade preventiva, e so uma cidade grande.
#
# Quem nao passa fica com score=None e `completude="insuficiente"`, e a
# interface o mostra numa lista propria. Nao responder ao IBGE nao pode
# esconder um municipio, mas tambem nao pode promove-lo.
MIN_COBERTURA_PESO = 0.60


# ---------------------------------------------------------------------------
# Componente I — impacto hidrico observado
# ---------------------------------------------------------------------------
# Perigos HIDRICOS. Deslizamento/queda de blocos ficam fora: sao geotecnicos,
# deflagrados por chuva mas com fisica, mapa de risco e obra de mitigacao
# diferentes. Misturar os dois num indice de "enchente" produz prioridade
# errada para os dois publicos.
PERIGOS_HIDRICOS = {
    "oc_inundacao": 0.30,           # transbordo de rio — o modo de 2024 no Guaiba/Taquari
    "oc_enchente_enxurrada": 0.30,  # enxurrada — o modo que mata em bacia pequena
    "oc_alagamento": 0.18,          # drenagem urbana saturada
    "oc_solapamento_margem": 0.12,  # erosao de margem: perda permanente de area
    "oc_erosao": 0.10,
}

# Severidade. Obito domina de proposito: uma escala de dano que trata morte
# como mais um item vira contabilidade de patrimonio.
DANOS = {
    "dano_obitos": 0.30,
    "dano_desaparecidos": 0.14,
    "dano_desabrigados": 0.16,
    "dano_feridos": 0.08,
    "areas_ilhadas": 0.12,   # isolamento: bloqueia socorro e reabastecimento
    "dano_viario": 0.10,
    "dano_barragens": 0.06,
    "risco_contaminacao_quimica": 0.04,
}

# ---------------------------------------------------------------------------
# Componente D — deficit de prevencao
# ---------------------------------------------------------------------------
# Pesos por gravidade do buraco. "Nao tem plano" pesa mais que "tem e nao
# executou", que pesa mais que "executou mas o alerta nao chegou".
DEFICIT_PLANO_AUSENTE = 0.40
DEFICIT_PLANO_NAO_EXECUTADO = 0.26
DEFICIT_SEM_ALERTA = 0.20
DEFICIT_SEM_CANAL_AUTOMATICO = 0.08  # nem SMS, nem app, nem sirene
DEFICIT_MOTIVOS = {  # motivos declarados de nao execucao, somados
    "falta_recurso_financeiro": 0.05,
    "falta_recurso_humano": 0.05,
    "falta_recurso_material": 0.05,
    "falta_sistema_alerta": 0.05,
    "falta_treinamento": 0.05,
}

# Alcance do alerta -> fracao NAO alcancada, que e o deficit. As faixas sao
# textuais no MUNIC; o ponto medio de cada faixa e a leitura mais honesta.
ALCANCE_PONTO_MEDIO = {
    "Menos de 100 a 90%": 0.95,
    "Menos de 90 a 80%": 0.85,
    "Menos de 80 a 50%": 0.65,
    "Menos de 50 a 30%": 0.40,
    "Menos de 30 a 10%": 0.20,
    "Menos de 10 a 5%": 0.075,
    "Menos de 5%": 0.025,
}
DEFICIT_ALCANCE_MAX = 0.18  # peso maximo quando o alerta nao alcancou ninguem

# ---------------------------------------------------------------------------
# Componente E — exposicao
# ---------------------------------------------------------------------------
GRUPOS_VULNERAVEIS = {
    "exp_favelas": 0.40,                  # ocupacao de margem e area de risco
    "exp_situacao_rua": 0.22,
    "exp_comunidades_tradicionais": 0.20,  # ribeirinhos, quilombolas, indigenas
    "exp_deficiencia": 0.18,               # evacuacao assistida
}
PESO_POPULACAO = 0.60
PESO_GRUPOS = 0.40


def _b(v: Any) -> bool | None:
    """pandas boolean/NA -> bool|None, sem transformar ausencia em False."""
    if v is None or v is pd.NA or (isinstance(v, float) and np.isnan(v)):
        return None
    return bool(v)


def _soma_pesos(row: pd.Series, pesos: dict[str, float]) -> tuple[float, list[str], bool]:
    """Soma os pesos das flags verdadeiras.

    Devolve (soma, rotulos_ativos, houve_resposta). `houve_resposta` distingue
    "respondeu que nao a tudo" (soma 0, medido) de "nao respondeu nada"
    (soma 0, ausente) — a diferenca entre um zero e um buraco.
    """
    total = 0.0
    ativos: list[str] = []
    respondeu = False
    for col, peso in pesos.items():
        val = _b(row.get(col))
        if val is None:
            continue
        respondeu = True
        if val:
            total += peso
            ativos.append(col)
    return total, ativos, respondeu


@dataclass
class Componente:
    """Valor em [0,1] + proveniencia + o que o produziu.

    `basis=None` com `valor=None` e um estado legitimo e frequente: significa
    "esta base nao responde por este municipio". A interface tem de mostrar o
    buraco, nao um zero.
    """

    valor: float | None
    basis: str | None
    detalhe: dict[str, Any] = field(default_factory=dict)


def _componente_impacto(row: pd.Series) -> Componente:
    atingido = _b(row.get("atingido"))
    if atingido is None:
        return Componente(None, None, {"motivo": "municipio nao respondeu ao suplemento"})
    if atingido is False:
        # Ausencia OBSERVADA de impacto: e um zero medido, nao um buraco.
        return Componente(0.0, "measured", {"atingido": False, "perigos": [], "danos": []})

    perigos, perigos_ativos, resp_p = _soma_pesos(row, PERIGOS_HIDRICOS)
    danos, danos_ativos, resp_d = _soma_pesos(row, DANOS)
    if not resp_p and not resp_d:
        return Componente(None, None, {"motivo": "atingido, mas sem detalhamento de perigo/dano"})

    valor = 0.55 * min(perigos, 1.0) + 0.45 * min(danos, 1.0)
    return Componente(
        round(float(min(valor, 1.0)), 4),
        "measured",
        {
            "atingido": True,
            "perigos": perigos_ativos,
            "danos": danos_ativos,
            "score_perigos": round(min(perigos, 1.0), 4),
            "score_danos": round(min(danos, 1.0), 4),
        },
    )


def _componente_deficit(row: pd.Series) -> Componente:
    plano = _b(row.get("plano_contingencia"))
    executado = _b(row.get("plano_executado"))
    alerta = _b(row.get("alerta_emitido"))

    if plano is None and alerta is None:
        return Componente(None, None, {"motivo": "sem resposta sobre plano nem alerta"})

    total = 0.0
    lacunas: list[str] = []

    if plano is False:
        total += DEFICIT_PLANO_AUSENTE
        lacunas.append("sem plano de contingencia")
    elif plano is True and executado is False:
        total += DEFICIT_PLANO_NAO_EXECUTADO
        lacunas.append("plano existe mas nao foi executado")

    motivos, motivos_ativos, _ = _soma_pesos(row, DEFICIT_MOTIVOS)
    total += motivos
    lacunas.extend(m.replace("_", " ") for m in motivos_ativos)

    if alerta is False:
        total += DEFICIT_SEM_ALERTA
        lacunas.append("nenhum alerta emitido a populacao")
    elif alerta is True:
        canais = [_b(row.get(c)) for c in ("alerta_sms", "alerta_app", "alerta_sirene")]
        if all(c is False for c in canais if c is not None) and any(c is not None for c in canais):
            total += DEFICIT_SEM_CANAL_AUTOMATICO
            lacunas.append("alerta sem canal automatico (SMS/app/sirene)")
        alcance = ALCANCE_PONTO_MEDIO.get(str(row.get("alerta_alcance", "")).strip())
        if alcance is not None:
            nao_alcancado = 1.0 - alcance
            total += DEFICIT_ALCANCE_MAX * nao_alcancado
            if nao_alcancado >= 0.5:
                lacunas.append(f"alerta alcancou apenas {int(alcance * 100)}% da populacao")

    return Componente(
        round(float(min(total, 1.0)), 4),
        "measured",
        {
            "plano_contingencia": plano,
            "plano_executado": executado,
            "alerta_emitido": alerta,
            "lacunas": lacunas,
        },
    )


def _componente_exposicao(row: pd.Series, pop_percentil: float | None) -> Componente:
    grupos, grupos_ativos, respondeu = _soma_pesos(row, GRUPOS_VULNERAVEIS)
    if pop_percentil is None and not respondeu:
        return Componente(None, None, {"motivo": "sem populacao nem resposta de grupos expostos"})

    partes = 0.0
    peso_total = 0.0
    if pop_percentil is not None:
        partes += PESO_POPULACAO * pop_percentil
        peso_total += PESO_POPULACAO
    if respondeu:
        partes += PESO_GRUPOS * min(grupos, 1.0)
        peso_total += PESO_GRUPOS

    valor = partes / peso_total if peso_total > 0 else None
    return Componente(
        None if valor is None else round(float(valor), 4),
        "measured",
        {
            "populacao_percentil": None if pop_percentil is None else round(pop_percentil, 4),
            "grupos_expostos": grupos_ativos,
        },
    )


# ---------------------------------------------------------------------------
# Componente H — perigo sazonal (estadual, uniforme, modelado)
# ---------------------------------------------------------------------------
def hazard_sazonal(oni: float | None) -> tuple[float, str]:
    """ONI -> intensidade em [0,1] + rotulo. MESMOS limiares de api/routers/risk.py.

    Duplicar a regra seria criar duas verdades; ela vive la porque o catalogo
    de perigos e o consumidor primario. Aqui so a traduzimos para escala
    continua, e a API injeta o valor — este modulo nao le o parquet do ONI.
    """
    if oni is None:
        return 0.0, "indisponivel"
    a = abs(oni)
    if oni >= 1.0:
        return min(1.0, 0.70 + 0.30 * min((a - 1.0) / 1.0, 1.0)), "El Nino forte — excesso de chuva"
    if oni >= 0.5:
        return 0.45, "El Nino fraco/moderado"
    if oni <= -0.5:
        return 0.25, "La Nina — deficit de chuva, perigo hidrico menor"
    return 0.20, "Neutro"


# ---------------------------------------------------------------------------
# Memoria hidrica — anexada a linha, FORA do indice
# ---------------------------------------------------------------------------
_AGUA_CATS = ("permanente", "sazonal", "perdida", "efemera")


def _bloco_aguas(row: pd.Series) -> dict[str, Any] | None:
    """Areas de agua do JRC (1984-2021) para o municipio, ou None se ausente.

    POR QUE ISTO NAO ENTRA NO INDICE COMPOSTO
    =========================================

    A tentacao e obvia: predisposicao de planicie e exatamente o que um indice
    de risco de cheia deveria pesar, o dado e medido e e independente das
    outras fontes. Mesmo assim fica de fora da v1 do indice, por uma razao
    especifica e nao por cautela generica.

    O RS tem ~1,1 milhao de hectares de arroz irrigado por inundacao, quase
    todo na fronteira oeste e na campanha. Lavoura alagada e agua sazonal para
    um sensor optico de 30 m — indistinguivel de banhado. Uruguaiana, Itaqui e
    Sao Borja lideram `sazonal` e `efemera` por lavoura, nao por varzea de
    risco. Dobrar essa variavel dentro do indice reordenaria a lista de
    prioridade preventiva em favor de municipios arrozeiros, e o faria sem que
    ninguem visse a causa.

    Separar `perdida` do resto ajuda (arroz ativo nao aparece como agua
    perdida) mas nao resolve: lavoura abandonada aparece. Sem uma mascara de
    agricultura irrigada — que exigiria MapBiomas e outra ingestao — o
    confundimento fica sem quantificacao.

    Entao a camada entra como DIMENSAO PARALELA de leitura, com o cruzamento
    contra 2024 explicito, e o indice segue como estava. Mudar um indice
    publicado por causa de uma variavel confundida e exatamente o que a
    disciplina de ADR deste projeto existe para impedir.
    """
    if "agua_perdida_km2" not in row.index or pd.isna(row.get("agua_perdida_km2")):
        return None
    out: dict[str, Any] = {}
    for cat in _AGUA_CATS:
        km2 = row.get(f"agua_{cat}_km2")
        frac = row.get(f"frac_{cat}")
        out[cat] = {
            "km2": None if pd.isna(km2) else round(float(km2), 2),
            "frac": None if pd.isna(frac) else round(float(frac), 5),
        }
    out["area_grade_km2"] = (
        None if pd.isna(row.get("area_grade_km2")) else round(float(row["area_grade_km2"]), 1)
    )
    # "Ja foi agua e hoje nao e" — a leitura que responde a pergunta original.
    perdida = out["perdida"]["km2"] or 0.0
    efemera = out["efemera"]["km2"] or 0.0
    area = out["area_grade_km2"] or 0.0
    out["memoria_hidrica_km2"] = round(perdida + efemera, 2)
    out["memoria_hidrica_frac"] = round((perdida + efemera) / area, 5) if area > 0 else None
    out["basis"] = "measured"
    return out


# ---------------------------------------------------------------------------
# Cenarios de horizonte — o que da para dizer sobre 2026 e sobre 2027
# ---------------------------------------------------------------------------
#
# A pergunta "e a previsao para 2026 e 2027?" tem DUAS respostas diferentes, e
# a diferenca entre elas e o conteudo mais importante desta camada.
#
# 2026 (OND): existe previsao oficial. O boletim ENSO do CPC cobre a
#   temporada-alvo desta engine e declara probabilidade. Entra como CONTEXTO
#   (ADR-012): a previsao e do CPC, nao nossa — a engine local continua sem
#   modelo aceito pela ADR-007.
#
# 2027: NAO existe previsao ENSO defensavel. O horizonte util de previsao ENSO
#   e de ~6 a 9 meses, e a barreira de previsibilidade da primavera boreal
#   degrada justamente as previsoes que atravessam o primeiro semestre. Uma
#   previsao para OND/2027 emitida em agosto/2026 esta a 14 meses: fora de
#   qualquer skill publicada. Inventar um numero ali seria pior que o silencio.
#
#   A resposta correta para 2027 nao e um ONI previsto — e o cenario
#   ESTRUTURAL: impacto ja observado, deficit de prevencao e exposicao nao
#   expiram. Um municipio sem plano de contingencia em 2024 continua sem plano
#   em 2027 ate alguem escrever um. Isso e planejavel com anos de antecedencia
#   justamente porque nao depende de saber que ENSO vira.
CENARIOS: dict[str, dict[str, Any]] = {
    "atual": {
        "label": "Agora — ONI medido",
        "horizonte": "estado corrente",
        "basis": "measured",
        "fonte": "cpc_oni",
        "nota": "Multiplicador sazonal derivado do ONI da ultima temporada publicada.",
    },
    "ond2026": {
        "label": "OND 2026 — outlook do CPC",
        "horizonte": "out-dez 2026",
        "basis": "modeled",
        "fonte": "cpc_enso_advisory",
        # Ancorado no limiar que o PROPRIO boletim usa para "muito forte"
        # (ONI >= 2.0). Nao e um numero nosso, e a leitura da categoria que o
        # CPC declarou com 81% de probabilidade — e o payload leva a citacao.
        "oni_ancora": 2.0,
        "nota": (
            "Cenario ancorado no limiar de 'El Nino muito forte' (ONI >= 2.0) que o proprio "
            "boletim do CPC usa. A previsao e do CPC/NOAA, NAO desta engine: nenhum modelo "
            "local passou o criterio da ADR-007."
        ),
    },
    "estrutural": {
        "label": "Estrutural — sem componente sazonal",
        "horizonte": "2027 e adiante",
        "basis": "measured",
        "fonte": "ibge_munic_rs",
        "nota": (
            "Sem previsao ENSO: o horizonte util e de ~6-9 meses e a barreira de "
            "previsibilidade da primavera degrada o que atravessa o primeiro semestre. "
            "Para 2027 o instrumento correto e o risco estrutural — impacto observado, "
            "deficit de prevencao e exposicao nao expiram, e por isso sao planejaveis "
            "com anos de antecedencia."
        ),
    },
}


def _nivel(score: float) -> str:
    for corte, nome in CORTES:
        if score >= corte:
            return nome
    return NIVEL_PADRAO


# ---------------------------------------------------------------------------
# Montagem
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MunicipalRiskTable:
    rows: list[dict[str, Any]]
    as_of_source: str
    n_completo: int
    n_parcial: int
    n_insuficiente: int
    cenario: str
    cenario_spec: dict[str, Any]


def _percentil_log_populacao(pop: pd.Series) -> pd.Series:
    """Percentil sobre log(pop).

    Populacao no RS vai de ~800 a ~1,3 milhao. Em escala linear, Porto Alegre
    achata os outros 496 municipios contra o zero e o componente perde toda a
    resolucao no meio da distribuicao, que e onde as decisoes acontecem.
    """
    logs = np.log10(pop.astype(float).clip(lower=1.0))
    return logs.rank(pct=True)


def build_table(oni: float | None, cenario: str = "atual") -> MunicipalRiskTable:
    """Tabela de risco integrado para os 497 municipios.

    `oni` e injetado pelo chamador (API) — este modulo nao conhece DuckDB nem
    o layout do parquet de series. Fronteira de diretorio == fronteira de
    acoplamento (ARCHITECTURE §5).

    `cenario` escolhe o horizonte (ver CENARIOS):
      atual       — H do ONI medido
      ond2026     — H do outlook do CPC para a temporada-alvo
      estrutural  — SEM H: o indice vira 100*(0.38I + 0.34D + 0.28E), que e o
                    unico instrumento defensavel para 2027 e adiante
    """
    if cenario not in CENARIOS:
        raise ValueError(f"cenario desconhecido: {cenario!r}; disponiveis: {list(CENARIOS)}")
    if not MUNIC_PARQUET.exists():
        raise FileNotFoundError(
            f"{MUNIC_PARQUET} ausente — rode `python -m src.ingest.ibge_rs munic`"
        )
    df = pd.read_parquet(MUNIC_PARQUET)

    if POP_PARQUET.exists():
        pop_df = pd.read_parquet(POP_PARQUET)[["cod_mun", "populacao"]]
        df = df.drop(columns=["populacao"]).merge(pop_df, on="cod_mun", how="left")

    # Memoria hidrica (JRC 1984-2021). Anexada a linha, mas DELIBERADAMENTE
    # FORA do indice composto — ver `aguas` no payload e a nota em model_card.
    from src.risk import aguas as _aguas

    aguas_df = _aguas.load()
    if aguas_df is not None:
        df = df.merge(aguas_df, on="cod_mun", how="left")

    df["_pop_pct"] = _percentil_log_populacao(df["populacao"].fillna(df["populacao"].median()))

    spec = CENARIOS[cenario]
    if cenario == "estrutural":
        # Multiplicador 1.0 e H declarado ausente: o indice estrutural NAO e
        # "o indice com ENSO neutro", e o indice sem a dimensao sazonal. Usar
        # o piso 0.62 aqui faria o cenario de longo prazo parecer sempre mais
        # brando que o de curto, quando na verdade ele mede outra coisa.
        oni_efetivo = None
        h_valor, h_rotulo = 0.0, "fora do horizonte de previsao ENSO"
        multiplicador = 1.0
        h_basis = None
    else:
        oni_efetivo = spec.get("oni_ancora", oni)
        h_valor, h_rotulo = hazard_sazonal(oni_efetivo)
        multiplicador = PISO_SAZONAL + (1.0 - PISO_SAZONAL) * h_valor
        h_basis = spec["basis"] if oni_efetivo is not None else None

    rows: list[dict[str, Any]] = []
    completo = parcial = insuficiente = 0
    for _, row in df.iterrows():
        imp = _componente_impacto(row)
        defi = _componente_deficit(row)
        expo = _componente_exposicao(row, float(row["_pop_pct"]))

        presentes = {
            "impacto": imp.valor,
            "deficit": defi.valor,
            "exposicao": expo.valor,
        }
        disponiveis = {k: v for k, v in presentes.items() if v is not None}

        peso_disp = sum(PESOS[k] for k in disponiveis)
        tem_sinal = ("impacto" in disponiveis) or ("deficit" in disponiveis)

        if peso_disp < MIN_COBERTURA_PESO or not tem_sinal:
            # Nao ranqueavel. Ver MIN_COBERTURA_PESO: o municipio continua no
            # payload, com o motivo, mas sem numero — um "—" honesto vale mais
            # que um indice que so mede a propria lacuna.
            score = None
            nivel = None
            basis = None
            completude = "insuficiente"
            insuficiente += 1
        else:
            # Renormaliza sobre os componentes presentes em vez de tratar
            # ausente como zero. Tratar buraco como zero puxaria o municipio
            # para "baixo risco" exatamente por nao ter dado.
            base = sum(PESOS[k] * v for k, v in disponiveis.items()) / peso_disp
            score = round(100.0 * base * multiplicador, 1)
            nivel = _nivel(score)
            basis = "modeled"
            if len(disponiveis) == 3:
                completo += 1
                completude = "completo"
            else:
                parcial += 1
                completude = "parcial"

        rows.append({
            "cod_mun": int(row["cod_mun"]),
            "municipio": str(row["municipio"]),
            "populacao": None if pd.isna(row["populacao"]) else int(row["populacao"]),
            "aguas": _bloco_aguas(row),
            "score": score,
            "level": nivel,
            "basis": basis,
            "completude": completude,
            "componentes": {
                "impacto": {"valor": imp.valor, "basis": imp.basis, "detalhe": imp.detalhe},
                "deficit_prevencao": {"valor": defi.valor, "basis": defi.basis, "detalhe": defi.detalhe},
                "exposicao": {"valor": expo.valor, "basis": expo.basis, "detalhe": expo.detalhe},
                "perigo_sazonal": {
                    "valor": None if cenario == "estrutural" else round(h_valor, 4),
                    "basis": h_basis,
                    "detalhe": {
                        "oni": oni_efetivo,
                        "rotulo": h_rotulo,
                        "escopo": "estadual — uniforme para os 497 municipios",
                        "cenario": cenario,
                        "horizonte": spec["horizonte"],
                        "motivo": spec["nota"] if cenario == "estrutural" else None,
                    },
                },
                # Declarado no contrato justamente para que a ausencia seja
                # visivel. Ver LIMITES §3: nao existe base publica municipal de
                # manutencao de casa de bomba, dique ou comporta no RS.
                "manutencao_ativos": {
                    "valor": None,
                    "basis": None,
                    "detalhe": {
                        "motivo": "sem fonte publica municipal de estado de manutencao "
                                  "de casas de bomba, diques e comportas no RS",
                    },
                },
            },
        })

    # Desempate por codigo IBGE, nao so por score.
    #
    # O score e publicado com uma casa decimal, e nessa resolucao dezenas de
    # municipios empatam. Sem desempate explicito a ordem dos empatados vinha
    # da ordem de leitura do parquet, e como o multiplicador sazonal muda quais
    # pares empatam, o ranking se reorganizava sozinho quando o ONI mudava —
    # dando a impressao de que o perigo sazonal tem resolucao municipal, que e
    # exatamente a leitura falsa que este modulo tenta impedir. Com cod_mun
    # como criterio final a lista so muda quando o dado muda.
    rows.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0.0), r["cod_mun"]))

    # Saturacao do multiplicador. Quando o outlook e forte o bastante para
    # levar H a 1.0, o cenario sazonal produz EXATAMENTE os mesmos numeros que
    # o estrutural. Isso nao e coincidencia nem bug: significa que a previsao
    # nao aplica nenhum desconto, e a prioridade de curto prazo coincide com a
    # de longo. E uma leitura util e precisa ser dita — dois paineis com
    # numeros identicos e nenhuma explicacao parecem erro de software.
    saturado = multiplicador >= 0.999

    return MunicipalRiskTable(
        rows=rows,
        as_of_source="IBGE MUNIC 2024 — evento de 26/04/2024",
        n_completo=completo,
        n_parcial=parcial,
        n_insuficiente=insuficiente,
        cenario=cenario,
        cenario_spec={  # noqa: C408 — literal explicito e mais legivel aqui
            **spec,
            "h_valor": round(h_valor, 4),
            "h_rotulo": h_rotulo,
            "multiplicador": round(multiplicador, 4),
            "saturado": saturado,
            "leitura_saturacao": (
                "O multiplicador sazonal esta no teto (1.00): a previsao nao atenua nada, "
                "e a prioridade desta temporada coincide numericamente com a estrutural."
                if saturado and cenario != "estrutural"
                else None
            ),
        },
    )


def load_malha() -> dict | None:
    """GeoJSON da malha municipal, ou None se ainda nao ingerida."""
    if not MALHA_GEOJSON.exists():
        return None
    return json.loads(MALHA_GEOJSON.read_text(encoding="utf-8"))


def model_card() -> dict[str, Any]:
    """Ficha do modelo — vai no payload da API, nao so no docstring.

    Um indice composto sem os pesos publicados nao e auditavel: quem le nao
    consegue refazer a conta nem discordar com precisao. Publicar peso, corte
    e limite e o que separa instrumento de opiniao com casas decimais.
    """
    return {
        "version": MODEL_VERSION,
        "formula": "R = 100 * (0.38*I + 0.34*D + 0.28*E) * (0.62 + 0.38*H)",
        "pesos": PESOS,
        "piso_sazonal": PISO_SAZONAL,
        "cortes": {nome: corte for corte, nome in CORTES},
        "componentes": {
            "I": "impacto hidrico observado (MUNIC 2024) — measured",
            "D": "deficit de prevencao declarado (MUNIC 2024) — measured",
            "E": "exposicao: populacao log-percentil + grupos vulneraveis — measured",
            "H": "perigo sazonal ONI — modeled, ESTADUAL e uniforme",
        },
        "cenarios": {k: {kk: vv for kk, vv in v.items()} for k, v in CENARIOS.items()},
        "memoria_hidrica": {
            "fonte": "JRC Global Surface Water v1.4 (transitions), 1984-2021",
            "no_indice": False,
            "motivo_fora_do_indice": (
                "Agua sazonal de satelite nao distingue banhado de lavoura de arroz irrigada, "
                "e o RS tem ~1,1 milhao de ha de arroz por inundacao. Incluir a variavel "
                "reordenaria a prioridade em favor de municipios arrozeiros sem que a causa "
                "ficasse visivel. Entra como dimensao paralela ate existir mascara de "
                "agricultura irrigada."
            ),
            "leitura": (
                "agua perdida + efemera = terreno com precedente de agua entre 1984 e 2021 "
                "que hoje nao e agua no mapa oficial."
            ),
        },
        "horizonte_previsao": {
            "fonte_prospectiva": "CPC/NOAA ENSO Diagnostic Discussion (contexto, ADR-012)",
            "limite_util_meses": 9,
            "barreira": "previsibilidade da primavera boreal degrada previsoes que atravessam o 1o semestre",
            "consequencia": (
                "Ha outlook oficial para OND/2026. NAO ha previsao ENSO defensavel para 2027: "
                "para esse horizonte o instrumento correto e o cenario estrutural, que nao "
                "depende de saber qual ENSO vira."
            ),
        },
        "limites": [
            "Nao e previsao de evento: nenhuma camada desta engine antecipa cheia individual (ADR-013).",
            "A previsao prospectiva e do CPC/NOAA, nao desta engine: nenhum modelo local passou a ADR-007.",
            "Nao ha previsao ENSO defensavel para 2027 — horizonte util de ~9 meses e barreira da primavera.",
            "Retrato de um unico evento (26/04/2024): municipio poupado por trajetoria aparece com impacto baixo.",
            "Auto-declaracao municipal ao IBGE, com incentivo assimetrico entre relatar dano e relatar falha de prevencao.",
            "Sem manutencao de ativo fisico: casas de bomba, diques e comportas nao tem base publica municipal no RS.",
            "Sem resolucao intramunicipal: nao existe ponto de enchente por bairro nesta base.",
            "Memoria hidrica cobre 1984-2021 (satelite), NAO 150 anos, e nao entra no indice.",
            "A malha municipal do IBGE exclui as grandes lagoas: Patos e parte da Mirim nao entram nas areas por municipio.",
            "H e estadual e uniforme — desloca o nivel de todos, nunca reordena o ranking.",
            "Pesos sao escolha editorial declarada, nunca calibrada contra desfecho (nao ha alvo observavel de 'catastrofe evitada').",
        ],
        "fontes": ["ibge_munic_rs", "ibge_pop_rs", "ibge_malha_rs", "cpc_oni"],
    }
