"""Resposta, vulnerabilidade e recuperacao — o que acontece depois que enche.

O indice municipal (`src/risk/municipal.py`) responde "onde agir antes". Este
modulo responde as perguntas seguintes, que sao outras:

    Quem estava exposto?      — grupos declarados como atingidos em 2024
    A saude aguentou?         — estrutura, equipamento, atendimento suspenso
    Ha para onde levar?       — hospital e pronto-socorro instalados, e a que
                                distancia para quem nao tem
    Por quantos dias?         — autonomia logistica declarada
    O que foi entregue?       — resgate, abrigo, alimento, apoio psicologico

Por que fica FORA do indice de prioridade
=========================================

O indice mede risco ANTES do evento. Estas variaveis descrevem o DEPOIS: sao
consequencia e resposta, nao predisposicao. Somar as duas coisas produziria um
numero que sobe tanto por um municipio ser vulneravel quanto por ele ter sido
atingido — e a lista deixaria de responder "onde agir antes" para virar um
ranking de quem sofreu mais, que e outra pergunta e ja tem resposta propria.

O QUE NAO EXISTE, E ESTE MODULO NAO INVENTA
===========================================

leitos            CNES-LT do DATASUS e `.dbc` sem API. Aqui ha ESTABELECIMENTO,
                  nao leito: a razao entre um e outro varia de 10 a 400 entre
                  um hospital de interior e um terciario.
dias letivos      Nao ha base publica de dias letivos perdidos por municipio
                  no evento. O Censo Escolar conta matricula, nao interrupcao.
recuperacao       Nao ha serie publica de repasse por municipio para o evento
financeira        em granularidade utilizavel. O MUNIC pergunta apenas se
                  houve solicitacao de recurso via SUS (booleano).
recuperacao       O MUNIC registra se houve OFERTA de apoio psicologico. Nao
psicologica       registra alcance, duracao nem desfecho.
estrutural        Ha dano declarado por categoria, nao valor nem prazo de
                  reconstrucao.

Cada uma dessas lacunas aparece no payload com motivo, pelo mesmo principio de
`manutencao_ativos`: campo ausente parece campo que ninguem precisou; campo
nulo com motivo e divida declarada.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
INTERIM = REPO_ROOT / "data" / "interim"

MUNIC_PARQUET = INTERIM / "ibge_munic_rs.parquet"
CNES_PARQUET = INTERIM / "cnes_rs.parquet"
MALHA_GEOJSON = INTERIM / "ibge_malha_rs.geojson"

VERSION = "resposta-v1"


# ---------------------------------------------------------------------------
# Grupos vulneraveis declarados como atingidos
# ---------------------------------------------------------------------------
GRUPOS = {
    "exp_criancas": "criancas",
    "exp_gestantes": "gestantes",
    "exp_doencas_cronicas": "pessoas com doencas cronicas",
    "exp_deficiencia": "pessoas com deficiencia",
    "exp_favelas": "moradores de favelas e comunidades urbanas",
    "exp_situacao_rua": "populacao em situacao de rua",
    "exp_comunidades_tradicionais": "comunidades tradicionais",
    "exp_populacao_negra": "populacao negra",
    "exp_mulheres": "mulheres",
    "exp_lgbtqia": "populacao LGBTQIA+",
}

# ---------------------------------------------------------------------------
# Impacto sobre o sistema de saude
# ---------------------------------------------------------------------------
SAUDE = {
    "saude_estruturas_afetadas": "estruturas de unidades de saude afetadas",
    "saude_danos_equipamentos": "danos em equipamentos",
    "saude_atendimento_suspenso": "atendimento suspenso total ou parcialmente",
    "saude_remanejamento_pacientes": "demanda de remanejamento de pacientes",
    "saude_doencas_inundacao": "doencas ligadas a inundacao (leptospirose, dengue)",
    "saude_combustivel": "restricao de combustivel",
    "dano_acolhimento_institucional": "danos em acolhimento institucional",
}

# ---------------------------------------------------------------------------
# Resposta prestada
# ---------------------------------------------------------------------------
RESPOSTA = {
    "resp_equipes_resgate": "equipes de resgate acionadas",
    "resp_transporte_vitimas": "tratamento e transporte de vitimas",
    "resp_ambulancias": "apoio de ambulancias solicitado",
    "resp_abrigo": "abrigo para desalojados",
    "resp_apoio_psicologico": "apoio psicologico as vitimas",
    "resp_alimentos_agua": "abastecimento de alimentos e agua",
    "resp_farmacos": "controle e distribuicao de farmacos",
    "resp_medicamentos_atencao": "levantamento de demanda de medicamentos",
    "resp_recursos_sus": "solicitacao de recursos via SUS",
    "resp_visita_domiciliar": "visita domiciliar (focos de mosquito)",
    "resp_limpeza_vias": "limpeza de vias e retirada de animais mortos",
}

# ---------------------------------------------------------------------------
# Autonomia logistica — escalas ordinais do MUNIC
# ---------------------------------------------------------------------------
#
# Traduzir texto ordinal para numero e uma INTERPRETACAO, e por isso ela fica
# escrita aqui em vez de embutida no codigo: quem discordar da leitura pode
# apontar a linha exata.
#
# "Nao houve/nao necessitou" vira None, NAO 1.0. O municipio que nao precisou
# de resgate nao demonstrou capacidade de resgate — tratar isso como nota
# maxima premiaria quem foi poupado e enterraria quem foi testado, invertendo
# exatamente o sinal que a escala existe para medir.
NAO_APLICAVEL = {"não houve/não necessitou", "-", "recusa", "não sabe informar", "não informou",
                 "cooperação nunca avaliada"}

ESCALAS: dict[str, dict[str, float]] = {
    "log_tempo_primeira_resposta": {
        "logo após o início do evento": 1.0,
        "1 dia após o início": 0.65,
        "2 dias após o início": 0.45,
        "3 dias após o início": 0.3,
        "mais de 3 dias após o início": 0.15,
    },
    "log_recursos_durante": {
        "disponíveis conforme as necessidades": 1.0,
        "5% a menos": 0.85,
        "10% a menos": 0.7,
        "mais de 10% a menos": 0.4,
    },
    "log_cobertura_bairros": {
        "dentro de 12 horas excederam a necessidade": 1.0,
        "iguais à necessidade": 0.85,
        "inferiores em 15%": 0.6,
        "inferiores em 25% ou mais": 0.35,
    },
    "log_72h_criticas": {
        "excederam a procura": 1.0,
        "igual à procura": 0.85,
        "menor em 15%": 0.55,
        "menor em 20% ou mais": 0.3,
    },
    "log_cooperacao": {
        "articulação de todos os procedimentos e sistemas críticos da primeira resposta": 1.0,
        "existiram pequenas incompatibilidades, mas foram resolvidas": 0.7,
        "grandes incompatibilidades, mas foram resolvidas": 0.45,
        "grandes incompatibilidades e sem resolução": 0.15,
    },
    # Leitura declarada das duas escalas de fornecimento: a pergunta e por
    # quantos dias o municipio sustentou o atendimento diante da interrupcao.
    # "Excederam" = sustentou mais tempo que a interrupcao durou (melhor caso);
    # "N dias de interrupcao" = ficou N dias descoberto (pior conforme N cresce).
    "log_dias_fornecimento": {
        "excederam os dias de interrupção": 1.0,
        "igual aos dias de interrupção": 0.8,
        "1 dia de interrupção": 0.55,
        "2 dias de interrupção": 0.4,
        "3 dias de interrupção": 0.25,
        "mais de 3 dias de interrupção": 0.1,
    },
    "log_alimentacao": {
        "excederam os dias de interrupção": 1.0,
        "igual aos dias de interrupção": 0.8,
        "1 dia de interrupção": 0.55,
        "2 dias de interrupção": 0.4,
        "3 dias de interrupção": 0.25,
        "mais de 3 dias de interrupção": 0.1,
    },
}

ROTULO_ESCALA = {
    "log_tempo_primeira_resposta": "tempo ate a primeira resposta",
    "log_recursos_durante": "recursos disponiveis durante o evento",
    "log_cobertura_bairros": "cobertura dos bairros pelos socorristas",
    "log_72h_criticas": "capacidade nas 72h mais criticas",
    "log_cooperacao": "cooperacao entre procedimentos criticos",
    "log_dias_fornecimento": "dias de fornecimento sustentados",
    "log_alimentacao": "dias de alimentacao sustentados",
}


def _b(v: Any) -> bool | None:
    if v is None or v is pd.NA or (isinstance(v, float) and math.isnan(v)):
        return None
    return bool(v)


def _flags(row: pd.Series, mapa: dict[str, str]) -> tuple[list[str], int, bool]:
    """Rotulos ativos, total respondido e se houve alguma resposta."""
    ativos: list[str] = []
    respondidos = 0
    for col, rotulo in mapa.items():
        v = _b(row.get(col))
        if v is None:
            continue
        respondidos += 1
        if v:
            ativos.append(rotulo)
    return ativos, respondidos, respondidos > 0


def _autonomia(row: pd.Series) -> dict[str, Any]:
    """Indice de autonomia logistica: media das escalas APLICAVEIS.

    Media sobre o que se aplica, e nao sobre as sete: um municipio que precisou
    de duas capacidades e foi bem nas duas nao pode ser penalizado por nao ter
    sido testado nas outras cinco.
    """
    itens: list[dict[str, Any]] = []
    valores: list[float] = []
    for col, escala in ESCALAS.items():
        bruto = str(row.get(col, "")).strip()
        chave = bruto.lower()
        if chave in NAO_APLICAVEL or not bruto or bruto == "nan":
            itens.append({"id": col, "rotulo": ROTULO_ESCALA[col], "resposta": bruto or None,
                          "valor": None, "aplicavel": False})
            continue
        valor = escala.get(chave)
        itens.append({"id": col, "rotulo": ROTULO_ESCALA[col], "resposta": bruto,
                      "valor": valor, "aplicavel": valor is not None})
        if valor is not None:
            valores.append(valor)
    return {
        "indice": round(float(np.mean(valores)), 4) if valores else None,
        "n_aplicaveis": len(valores),
        "itens": itens,
        "basis": "measured" if valores else None,
    }


# ---------------------------------------------------------------------------
# Capacidade instalada e acesso
# ---------------------------------------------------------------------------
def _centroides() -> dict[int, tuple[float, float]]:
    """Centroide simples (media dos vertices) por municipio.

    Media de vertices, nao centroide de area: para medir distancia ATE a
    unidade mais proxima, a diferenca entre os dois e de poucos quilometros e
    nao muda nenhuma decisao — e evita arrastar shapely para o projeto.
    """
    geo = json.loads(MALHA_GEOJSON.read_text(encoding="utf-8"))
    out: dict[int, tuple[float, float]] = {}
    for f in geo["features"]:
        cod = int(f["properties"]["codarea"])
        g = f["geometry"]
        aneis = g["coordinates"] if g["type"] == "Polygon" else [r for p in g["coordinates"] for r in p]
        pts = [pt for anel in aneis for pt in anel]
        out[cod] = (
            float(np.mean([p[0] for p in pts])),
            float(np.mean([p[1] for p in pts])),
        )
    return out


def _haversine(lon1: float, lat1: float, lon2: np.ndarray, lat2: np.ndarray) -> np.ndarray:
    r = 6371.0
    p1, p2 = math.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + math.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


@dataclass(frozen=True)
class RespostaTable:
    rows: list[dict[str, Any]]
    resumo: dict[str, Any]
    lacunas: list[dict[str, str]] = field(default_factory=list)


LACUNAS = [
    {
        "id": "leitos",
        "titulo": "Contagem de leitos",
        "motivo": "CNES-LT do DATASUS e publicado em .dbc sem API. Aqui ha ESTABELECIMENTO, "
                  "nao leito: a razao entre os dois varia de 10 a 400 conforme o porte.",
    },
    {
        "id": "dias_letivos",
        "titulo": "Dias letivos perdidos",
        "motivo": "Nao ha base publica de interrupcao escolar por municipio no evento. "
                  "O Censo Escolar conta matricula, nao dias parados.",
    },
    {
        "id": "recuperacao_financeira",
        "titulo": "Recuperacao financeira",
        "motivo": "Sem serie publica de repasse por municipio para o evento. O MUNIC registra "
                  "apenas se houve solicitacao de recurso via SUS (sim/nao).",
    },
    {
        "id": "recuperacao_psicologica",
        "titulo": "Alcance do apoio psicologico",
        "motivo": "O MUNIC registra se houve OFERTA de apoio psicologico. Nao registra "
                  "alcance, duracao nem desfecho.",
    },
    {
        "id": "recuperacao_estrutural",
        "titulo": "Prazo e custo de reconstrucao",
        "motivo": "Ha dano declarado por categoria, sem valor nem prazo.",
    },
]


def build_table() -> RespostaTable:
    if not MUNIC_PARQUET.exists():
        raise FileNotFoundError(f"{MUNIC_PARQUET} ausente — rode `python -m src.ingest.ibge_rs munic`")
    df = pd.read_parquet(MUNIC_PARQUET)

    # Capacidade instalada por municipio. O CNES usa codigo de 6 digitos.
    cnes = pd.read_parquet(CNES_PARQUET) if CNES_PARQUET.exists() else None
    por_mun: dict[int, dict[str, Any]] = {}
    unidades_coord: list[tuple[float, float]] = []
    if cnes is not None:
        validos = cnes.dropna(subset=["lat", "lon"])
        unidades_coord = list(zip(validos["lon"].astype(float), validos["lat"].astype(float)))
        for cod6, grupo in cnes.groupby("cod_mun6"):
            por_mun[int(cod6)] = {
                "total": int(len(grupo)),
                "hospitais": int((grupo["tipo"].isin(["hospital_geral", "hospital_especializado"])).sum()),
                "urgencia": int((~grupo["tipo"].isin(["hospital_geral", "hospital_especializado"])).sum()),
                "centro_cirurgico": int(pd.to_numeric(grupo["centro_cirurgico"], errors="coerce").fillna(0).sum()),
                "centro_obstetrico": int(pd.to_numeric(grupo["centro_obstetrico"], errors="coerce").fillna(0).sum()),
            }

    centroides = _centroides() if MALHA_GEOJSON.exists() else {}
    lons = np.array([c[0] for c in unidades_coord]) if unidades_coord else np.array([])
    lats = np.array([c[1] for c in unidades_coord]) if unidades_coord else np.array([])

    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        cod = int(row["cod_mun"])
        cod6 = cod // 10  # 7 digitos -> 6 (o CNES nao usa o verificador)
        cap = por_mun.get(cod6)

        dist_km = None
        if cap is None and cod in centroides and lons.size:
            lon, lat = centroides[cod]
            dist_km = round(float(_haversine(lon, lat, lons, lats).min()), 1)

        grupos, grupos_resp, grupos_ok = _flags(row, GRUPOS)
        saude, saude_resp, saude_ok = _flags(row, SAUDE)
        resp, resp_resp, resp_ok = _flags(row, RESPOSTA)
        autonomia = _autonomia(row)

        pop = None if pd.isna(row.get("populacao")) else int(row["populacao"])
        rows.append({
            "cod_mun": cod,
            "municipio": str(row["municipio"]),
            "populacao": pop,
            "capacidade": {
                "unidade": "estabelecimentos",  # NUNCA "leitos" — ver LACUNAS
                "total": cap["total"] if cap else 0,
                "hospitais": cap["hospitais"] if cap else 0,
                "urgencia": cap["urgencia"] if cap else 0,
                "centro_cirurgico": cap["centro_cirurgico"] if cap else 0,
                "centro_obstetrico": cap["centro_obstetrico"] if cap else 0,
                "por_100k": (
                    round(cap["total"] / pop * 100_000, 2) if cap and pop else (0.0 if pop else None)
                ),
                "km_ate_unidade_mais_proxima": dist_km,
                "basis": "measured" if cnes is not None else None,
            },
            "vulneraveis": {
                "grupos": grupos,
                "n_respondidos": grupos_resp,
                "basis": "measured" if grupos_ok else None,
            },
            "saude": {
                "impactos": saude,
                "n_respondidos": saude_resp,
                "basis": "measured" if saude_ok else None,
            },
            "resposta": {
                "prestadas": resp,
                "n_respondidos": resp_resp,
                "apoio_psicologico": _b(row.get("resp_apoio_psicologico")),
                "basis": "measured" if resp_ok else None,
            },
            "autonomia_logistica": autonomia,
        })

    sem_unidade = sum(1 for r in rows if r["capacidade"]["total"] == 0)
    com_psico = sum(1 for r in rows if r["resposta"]["apoio_psicologico"] is True)
    sem_psico = sum(1 for r in rows if r["resposta"]["apoio_psicologico"] is False)
    saude_afetada = sum(1 for r in rows if r["saude"]["impactos"])
    autonomias = [r["autonomia_logistica"]["indice"] for r in rows if r["autonomia_logistica"]["indice"] is not None]

    resumo = {
        "version": VERSION,
        "n_municipios": len(rows),
        "capacidade": {
            "unidade": "estabelecimentos",
            "aviso": "NAO e contagem de leitos — ver lacunas.",
            "total_estabelecimentos": sum(r["capacidade"]["total"] for r in rows),
            "municipios_sem_unidade": sem_unidade,
            "km_mediano_ate_unidade": (
                round(float(np.median([r["capacidade"]["km_ate_unidade_mais_proxima"]
                                       for r in rows
                                       if r["capacidade"]["km_ate_unidade_mais_proxima"] is not None])), 1)
                if sem_unidade else None
            ),
        },
        "saude_afetada": saude_afetada,
        "apoio_psicologico": {"ofereceram": com_psico, "nao_ofereceram": sem_psico},
        "autonomia": {
            "n_avaliados": len(autonomias),
            "mediana": round(float(np.median(autonomias)), 3) if autonomias else None,
        },
        "fora_do_indice": (
            "Estas variaveis descrevem o DEPOIS do evento — consequencia e resposta, nao "
            "predisposicao. Somá-las ao indice de prioridade transformaria a lista de "
            "'onde agir antes' num ranking de quem sofreu mais."
        ),
    }
    return RespostaTable(rows=rows, resumo=resumo, lacunas=LACUNAS)
