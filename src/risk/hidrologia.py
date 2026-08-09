"""Modelo hidrologico municipal — quanto da chuva vira enxurrada.

O QUE ESTA CAMADA FAZ, EM UMA FRASE
===================================

Pega a chuva que cai e devolve a parte dela que NAO infiltra, por municipio,
usando o solo, a cobertura e o relevo que o IBGE mapeou — e devolve tambem o
tamanho da propria ignorancia, que aqui e grande e precisa aparecer.

Ate esta camada a central sabia dizer "vai chover acima da media" e "este
municipio ja alagou". Nao sabia ligar as duas pontas. A ligacao e fisica e tem
nome ha setenta anos: chuva menos infiltracao e escoamento, e infiltracao
depende do que esta debaixo da chuva.

O METODO, E POR QUE ESTE
========================

Curve Number (SCS/NRCS). E o metodo de balanco de eventos mais usado do mundo,
e a escolha aqui nao e por qualidade: e por AUDITABILIDADE. O CN tem tabela
publica, entra em manual de drenagem de prefeitura, e qualquer engenheiro que
discorde do numero pode apontar a linha da tabela que discorda. Um modelo
distribuido calibrado seria melhor fisica e pior instrumento publico: ninguem
de fora conseguiria contestar um parametro.

    S = 25400/CN - 254            (mm, capacidade de retencao)
    Ia = 0,2 S                    (perda inicial)
    Q = (P - Ia)^2 / (P - Ia + S) se P > Ia, senao 0

O QUE O CN NAO E
================

Nao e previsao de cheia. Q e lamina escoada num evento, nao vazao, nao cota,
nao area inundada. Entre o escoamento gerado e a agua na porta de alguem ha o
caminho, o tempo, a rede de drenagem e o nivel do corpo receptor — e no RS o
receptor costuma ser laguna governada por vento, onde a agua chega e nao sai.
Um municipio pode gerar pouco escoamento e inundar mesmo assim, por remanso.

Nao e valido para o lote. A menor unidade honesta e o municipio, porque o
insumo e cartografia 1:250.000.

E, sobretudo, o CN e um metodo de EVENTO calibrado em bacias agricolas
americanas dos anos 1950. A relacao Ia = 0,2S tem literatura extensa mostrando
que 0,05S ajusta melhor em muitos lugares. Manter 0,2S aqui e escolha de
comparabilidade com o manual de drenagem que a prefeitura ja usa, nao
afirmacao de que 0,2 e o certo — e por isso o payload carrega a razao usada.

A FRONTEIRA MEDIDO/MODELADO, QUE AQUI E ESTREITA
================================================

Medido: a fracao de cada combinacao de solo, cobertura e relevo (IBGE/BDiA),
a fracao construida (GHSL) e a serie diaria de chuva (GHCN).

Modelado, e e a maior parte: o grupo hidrologico de cada solo, o CN de cada
par (grupo, cobertura), a chuva de projeto por Gumbel, e o proprio balanco.
Nenhum desses passos e observacao. Por isso o payload inteiro sai `modeled`,
e cada numero derivado carrega o parametro que o gerou.

O que faria esta camada virar `measured`: serie fluviometrica da ANA para
calibrar CN por bacia. Ela existe (`ana_fluvio` no catalogo de fontes, hoje
fora de escopo) e enquanto nao for ingerida, o CN daqui e tabela, nao ajuste.
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

CRUZADO_PARQUET = INTERIM / "bdia_cruzado_rs.parquet"
CONSTRUIDA_PARQUET = INTERIM / "ghsl_built_rs.parquet"
GHCN_DIARIO = INTERIM / "ghcn_rs_diario.parquet"
GHCN_ESTACOES = INTERIM / "ghcn_rs_estacoes.parquet"

VERSION = "hidrologia-v1"

# Razao de perda inicial. Ver o cabecalho: 0,2 e a convencao do manual, nao
# uma medida. Viaja no payload para que trocar por 0,05 seja uma decisao
# visivel, e nao uma edicao de codigo que ninguem nota.
RAZAO_IA = 0.20

# Tempos de retorno publicados. 2 anos e a cheia ordinaria (a que molha todo
# ano e define drenagem urbana); 100 anos e o que aparece em projeto de obra.
TR_ANOS = (2, 10, 25, 100)

# CN de superficie impermeavel e de agua livre. 98 e o valor de tabela para
# pavimento; 100 e agua, onde toda a chuva ja esta no corpo receptor.
CN_IMPERMEAVEL = 98.0
CN_AGUA = 100.0


# ---------------------------------------------------------------------------
# 1. Solo -> grupo hidrologico
# ---------------------------------------------------------------------------
# O CN nao le "Argissolo": le grupo A, B, C ou D, definido pela capacidade de
# infiltracao do perfil saturado. Traduzir a ordem do SiBCS para o grupo e o
# passo mais carregado de julgamento desta camada inteira, e ele nao vive na
# ingestao de proposito.
#
# A base da traducao e a classificacao hidrologica de solos brasileiros que a
# literatura nacional consolidou (Sartori, Genovez e Lombardi Neto, 2005) e a
# textura declarada em cada poligono, que e o que fisicamente governa. A regra
# aplicada aqui, na ordem:
#
#   1. Solo RASO ou com impedimento manda mais que a ordem. Neossolo Litolico
#      sobre rocha, afloramento e solo com horizonte plintico nao tem para
#      onde infiltrar: D, mesmo com textura arenosa.
#   2. Solo hidromorfico (Gleissolo, Organossolo) esta saturado por definicao
#      no evento que importa: D.
#   3. Mudanca textural abrupta (Planossolo, Luvissolo, e o Argissolo cuja
#      textura declarada salta de arenosa para argilosa) cria lencol suspenso
#      e escoamento sub-superficial rapido: C ou D.
#   4. Solo profundo e poroso (Latossolo, Nitossolo) e A ou B conforme a
#      textura — e aqui a intuicao engana: no Latossolo MUITO ARGILOSO a
#      estrutura granular da alta condutividade, entao argila pesada vira A,
#      nao D. Essa e a diferenca entre a tabela americana e a brasileira, e
#      ignora-la inverte o resultado no planalto inteiro.
#
# Onde a ordem nao decide, decide a textura. Onde nem uma nem outra existem
# (poligono de agua ou area urbana), o grupo e None e o CN vem por outro
# caminho — nunca por preenchimento com a media.
GRUPO_POR_ORDEM: dict[str, str] = {
    "GLEISSOLO": "D",
    "ORGANOSSOLO": "D",
    "PLINTOSSOLO": "D",
    "VERTISSOLO": "D",
    "PLANOSSOLO": "D",
    "LUVISSOLO": "C",
    "CAMBISSOLO": "C",
    "CHERNOSSOLO": "C",
    "ESPODOSSOLO": "C",
    "ARGISSOLO": "B",
    "NITOSSOLO": "B",
    "LATOSSOLO": "A",
    "DUNAS": "A",
    "AFLORAMENTOS DE ROCHAS": "D",
}

# Neossolo depende inteiramente da subordem, e o parquet so traz a ordem — a
# subordem esta na legenda. Litolico e raso (D); Quartzarenico e areia profunda
# (A); Fluvico e varzea (C); Regolitico fica no meio (B).
GRUPO_NEOSSOLO: tuple[tuple[str, str], ...] = (
    ("LITOLICO", "D"),
    ("QUARTZAREN", "A"),
    ("FLUVICO", "C"),
    ("REGOLITICO", "B"),
)


def _sem_acento(s: str) -> str:
    import unicodedata

    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    ).upper()


def grupo_hidrologico(ordem: str | None, legenda: str | None, textura: str | None) -> str | None:
    """Grupo A-D do solo, ou None quando o poligono nao e solo.

    None e resposta legitima e frequente: corpo d'agua e area urbana ocupam
    ~8% do estado no mapa pedologico e nao tem grupo. Devolver 'C' por
    conveniencia colocaria terreno inexistente na conta de infiltracao.
    """
    leg = _sem_acento(legenda or "")
    ordem_n = _sem_acento(ordem or "")
    tex = _sem_acento(textura or "")

    if not ordem_n:
        return None

    if ordem_n == "NEOSSOLO":
        for marca, grupo in GRUPO_NEOSSOLO:
            if marca in leg:
                return grupo
        # Neossolo sem subordem legivel: fica em C. Nao e chute confortavel —
        # e o valor que erra menos entre um raso (D) e uma areia (A), e a
        # linha aparece em `avisos` para nao passar como se fosse conhecida.
        return "C"

    base = GRUPO_POR_ORDEM.get(ordem_n)
    if base is None:
        return None

    # Ajuste por textura, so onde ela muda o comportamento de verdade.
    if base == "A" and tex.startswith("MEDIA") and "ARGILOSA" not in tex:
        # Latossolo de textura media perde a estrutura granular que sustentava
        # o grupo A.
        return "B"
    if base == "B" and tex.startswith("ARENOSA/") and "ARGILOSA" in tex:
        # Salto arenosa -> argilosa no perfil e mudanca textural abrupta, com
        # ou sem o nome Planossolo na legenda.
        return "C"
    return base


# ---------------------------------------------------------------------------
# 2. Cobertura -> classe de CN
# ---------------------------------------------------------------------------
# As classes abaixo sao as linhas da tabela do NRCS que existem no RS. Nao ha
# "condicao hidrologica" no dado do IBGE — a tabela original separa boa, media
# e ma condicao pela cobertura do solo e pelo manejo, que o mapa nao ve. A
# escolha aqui e assumir condicao MEDIA em tudo que e uso antropico e boa em
# vegetacao nativa remanescente, e declarar isso: assumir boa condicao em
# lavoura seria otimismo embutido no numero.
CLASSES_COBERTURA: dict[str, dict[str, Any]] = {
    "agua": {"label": "corpo d'agua", "cn": (CN_AGUA,) * 4},
    "urbano": {
        "label": "area urbana (parcela permeavel)",
        # A parcela impermeavel NAO entra aqui — entra depois, pelo GHSL, que
        # mede. Somar as duas coisas na mesma linha contaria o asfalto duas
        # vezes: uma no rotulo urbano do IBGE, outra na medicao de satelite.
        "cn": (49.0, 69.0, 79.0, 84.0),
    },
    "floresta_nativa": {"label": "floresta nativa", "cn": (30.0, 55.0, 70.0, 77.0)},
    "vegetacao_secundaria": {"label": "vegetacao secundaria", "cn": (36.0, 60.0, 73.0, 79.0)},
    "silvicultura": {
        "label": "silvicultura (pinus/eucalipto)",
        # Condicao ma, nao boa: plantio comercial costuma ter sub-bosque
        # suprimido e serrapilheira removida ou queimada entre ciclos, e o
        # solo exposto no ano do corte raso e o que governa o evento extremo.
        "cn": (45.0, 66.0, 77.0, 83.0),
    },
    "campo_nativo": {"label": "campo e estepe", "cn": (39.0, 61.0, 74.0, 80.0)},
    "pastagem": {"label": "pecuaria (pastagem)", "cn": (49.0, 69.0, 79.0, 84.0)},
    "agricultura": {"label": "lavoura", "cn": (67.0, 78.0, 85.0, 89.0)},
    "agropecuaria": {
        "label": "mosaico agropecuario",
        # O IBGE usa "Agropecuaria" para o mosaico que nao se consegue separar
        # em lavoura e pasto — e ele cobre 200 mil km2, tres quartos do estado.
        # O CN e a media das duas linhas que ele mistura, e essa media e a
        # maior fonte de incerteza do modelo inteiro. Aparece em `avisos`.
        "cn": (58.0, 74.0, 82.0, 87.0),
    },
    "banhado": {
        "label": "formacao pioneira / banhado",
        # Solo saturado durante o evento: a capacidade de retencao ja foi
        # consumida antes de a chuva comecar.
        "cn": (80.0, 85.0, 89.0, 92.0),
    },
    "dunas": {"label": "dunas e restinga", "cn": (25.0, 40.0, 60.0, 70.0)},
}

_ORDEM_GRUPO = {"A": 0, "B": 1, "C": 2, "D": 3}


def classe_cobertura(legenda: str | None, uso_antropico: str | None) -> str:
    """Classe de CN a partir da legenda de vegetacao e do uso antropico.

    A ordem dos testes importa: uso antropico vence fitofisionomia, porque o
    mapa registra a vegetacao ORIGINAL da area junto com o uso que a
    substituiu. Ler a floresta que havia como se ainda estivesse la seria o
    erro mais caro possivel aqui — subestimaria o escoamento exatamente onde
    ele mais cresceu.
    """
    leg = _sem_acento(legenda or "")
    uso = _sem_acento(uso_antropico or "")
    texto = f"{uso} {leg}"

    if "CORPO D'AGUA" in leg or "CORPO DAGUA" in leg:
        return "agua"
    if "URBAN" in texto:
        return "urbano"
    if "DUNA" in texto:
        return "dunas"
    if "FLORESTAMENTO" in texto or "REFLORESTAMENTO" in texto:
        return "silvicultura"
    # AGROPECUARIA vem ANTES de PECUARIA, e a ordem nao e estetica: "PECUARIA"
    # e substring de "AGROPECUARIA". Com o teste invertido, o mosaico que cobre
    # tres quartos do estado inteiro caia na linha de pastagem, e o CN do RS
    # despencava uns dez pontos sem que nada no caminho acusasse. O teste
    # `test_agropecuaria_nao_cai_em_pastagem` existe por causa disso.
    if "AGROPECUARIA" in texto:
        return "agropecuaria"
    if "AGRICULTURA" in texto:
        return "agricultura"
    if "PECUARIA" in texto or "PASTAGEM" in texto:
        return "pastagem"
    if "SECUNDARIA" in texto:
        return "vegetacao_secundaria"
    if "PIONEIRA" in leg:
        return "banhado"
    if "FLORESTA" in leg:
        return "floresta_nativa"
    if "ESTEPE" in leg or "SAVANA" in leg or "CAMPO" in leg:
        return "campo_nativo"
    if "REFUGIO" in leg or "VEGETACAO" in leg:
        return "vegetacao_secundaria"
    # Sem cobertura legivel o pedaco entra como mosaico agropecuario, que e o
    # uso majoritario do estado, e a linha e contada em `avisos`.
    return "agropecuaria"


def cn_de(grupo: str | None, cobertura: str) -> float | None:
    """CN da combinacao (grupo, cobertura), em condicao de umidade media."""
    cls = CLASSES_COBERTURA[cobertura]
    if cobertura == "agua":
        return CN_AGUA
    if grupo is None:
        # Sem grupo o CN so e definido para agua e urbano — e para urbano o
        # solo abaixo continua existindo, entao usamos B, o mais comum do
        # estado, e a linha e declarada como suposicao.
        return cls["cn"][_ORDEM_GRUPO["B"]] if cobertura == "urbano" else None
    return cls["cn"][_ORDEM_GRUPO[grupo]]


def cn_umidade_alta(cn2: float) -> float:
    """CN em condicao de umidade ANTECEDENTE alta (AMC III).

    O evento que interessa no RS raramente e a primeira chuva: e a terceira em
    dez dias, com o perfil ja cheio. A conversao classica

        CN3 = 23*CN2 / (10 + 0,13*CN2)

    leva um CN2 de 74 para 87 — o escoamento praticamente dobra sem que uma
    gota a mais tenha caido. Publicar so o CN2 descreveria um estado que quase
    nunca e o do desastre.
    """
    return 23.0 * cn2 / (10.0 + 0.13 * cn2)


def escoamento_mm(p_mm: float, cn: float, razao_ia: float = RAZAO_IA) -> float:
    """Lamina escoada de um evento de chuva `p_mm` sobre um terreno de `cn`."""
    if cn <= 0:
        return 0.0
    s = 25400.0 / cn - 254.0
    ia = razao_ia * s
    if p_mm <= ia:
        return 0.0
    return (p_mm - ia) ** 2 / (p_mm - ia + s)


# ---------------------------------------------------------------------------
# 3. Chuva de projeto
# ---------------------------------------------------------------------------
def _gumbel(maximos: np.ndarray, tr: int) -> float:
    """Quantil de Gumbel por momentos, para tempo de retorno `tr`.

    Momentos e nao maxima verossimilhanca de proposito: com 30-60 maximos
    anuais as duas praticamente coincidem, e momentos nao tem modo de falha
    por nao-convergencia silenciosa num loop sobre 66 estacoes.
    """
    mu_amostral = float(np.mean(maximos))
    sigma = float(np.std(maximos, ddof=1))
    beta = sigma * math.sqrt(6.0) / math.pi
    mu = mu_amostral - 0.5772 * beta
    return mu - beta * math.log(-math.log(1.0 - 1.0 / tr))


@dataclass(frozen=True)
class ChuvaProjeto:
    station_id: str
    estacao: str
    km: float
    anos: int
    por_tr: dict[int, float]


def chuvas_de_projeto(min_anos: int = 20) -> dict[str, ChuvaProjeto]:
    """P24h por tempo de retorno, por estacao do GHCN.

    Estacao com menos de `min_anos` maximos anuais fica de fora: ajustar
    Gumbel em 8 pontos devolve um numero, e o numero e ficcao.
    """
    diario = pd.read_parquet(GHCN_DIARIO)
    estacoes = pd.read_parquet(GHCN_ESTACOES)
    diario["ano"] = pd.to_datetime(diario["data"]).dt.year
    # Ano com cobertura parcial NAO entra. O maximo de um ano com 60 dias
    # observados nao e o maximo daquele ano — e o maior de uma amostra
    # pequena, quase sempre menor que o verdadeiro. Misturar esses anos com
    # os completos puxa toda a distribuicao de Gumbel para baixo, e o efeito
    # e pior justamente nas estacoes urbanas recentes: Porto Alegre saia com
    # chuva de TR 2 de 32 mm, um terco do plausivel, sem nenhum sinal de erro.
    agregado = diario.groupby(["station_id", "ano"]).prcp_mm.agg(["max", "count"]).reset_index()
    maximos = agregado[agregado["count"] >= 300].rename(columns={"max": "prcp_mm"})

    saida: dict[str, ChuvaProjeto] = {}
    nomes = {r.station_id: r.nome for r in estacoes.itertuples()}
    for sid, g in maximos.groupby("station_id"):
        serie = g.prcp_mm.dropna().to_numpy()
        if len(serie) < min_anos or float(np.std(serie, ddof=1)) <= 0:
            continue
        saida[sid] = ChuvaProjeto(
            station_id=sid,
            estacao=nomes.get(sid, sid),
            km=float("nan"),
            anos=len(serie),
            por_tr={tr: round(_gumbel(serie, tr), 1) for tr in TR_ANOS},
        )
    return saida


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# 4. Tempo de concentracao, em ordinal
# ---------------------------------------------------------------------------
# Nao ha comprimento de talvegue nem declividade media de bacia no dado — e sem
# os dois nao existe tempo de concentracao em minutos. O que existe e a
# densidade de drenagem e a forma do relevo, que ordenam a resposta sem
# quantifica-la: bacia com drenagem muito alta em relevo forte ondulado
# concentra antes que bacia de drenagem baixa em planicie.
#
# O resultado e ORDINAL e e rotulado como tal. Publicar "tempo de concentracao
# de 3,4 h" a partir disto seria inventar precisao; publicar "resposta rapida"
# e o que o dado sustenta.
PESO_DRENAGEM = {"muito alta": 4, "alta": 3, "media": 2, "baixa": 1, "muito baixa": 0}
PESO_RELEVO = {
    "montanhoso e escarpado": 4, "montanhoso": 4, "montanhoso e forte ondulado": 4,
    "forte ondulado e montanhoso": 4, "forte ondulado": 3, "forte ondulado e ondulado": 3,
    "ondulado e forte ondulado": 3, "ondulado": 2, "ondulado e suave ondulado": 2,
    "suave ondulado e ondulado": 2, "suave ondulado": 1, "suave ondulado e plano": 1,
    "plano e suave ondulado": 1, "plano": 0,
}
RESPOSTA_LABEL = ((6, "muito rapida"), (4, "rapida"), (2, "moderada"), (0, "lenta"))

DEM_PARQUET = INTERIM / "copernicus_dem_rs.parquet"

# Faixas de declividade MEDIDA equivalentes aos pesos do adjetivo. Quando o DEM
# existe, ele substitui `PESO_RELEVO` — nao por ser mais novo, mas porque o
# adjetivo da carta descreve o poligono inteiro pela feicao predominante em
# area, e a encosta que governa a resposta raramente e a que predomina.
PESO_DECLIVIDADE = ((45.0, 4), (20.0, 3), (8.0, 2), (3.0, 1), (0.0, 0))


def _relevo_medido() -> dict[int, float]:
    """Declividade media por municipio (Copernicus DEM 90 m), se ingerida."""
    if not DEM_PARQUET.exists():
        return {}
    d = pd.read_parquet(DEM_PARQUET)
    return {int(r.cod_mun): float(r.declividade_media_pct) for r in d.itertuples()}


def _peso_declividade(pct: float) -> int:
    for corte, peso in PESO_DECLIVIDADE:
        if pct >= corte:
            return peso
    return 0


def _resposta_ordinal(
    linhas: pd.DataFrame, declividade_pct: float | None = None
) -> tuple[str | None, float | None]:
    """Rotulo de velocidade de concentracao, ponderado por area.

    Com declividade medida disponivel, ela entra no lugar do adjetivo da carta
    — o mesmo peso, apurado da mesma faixa de porcentagem, mas a partir do que
    o terreno tem e nao do que a legenda diz que ele predominantemente e.
    """
    peso_relevo_medido = (
        _peso_declividade(declividade_pct) if declividade_pct is not None else None
    )
    pesos, areas = [], []
    for r in linhas.itertuples():
        d = PESO_DRENAGEM.get(_sem_acento(str(r.geom_dens_dren or "")).lower())
        v = (peso_relevo_medido if peso_relevo_medido is not None
             else PESO_RELEVO.get(str(r.pedo_relevo or "").strip().lower()))
        if d is None and v is None:
            continue
        pesos.append((d if d is not None else 0) + (v if v is not None else 0))
        areas.append(r.km2)
    if not areas:
        return None, None
    escore = float(np.average(pesos, weights=areas))
    for corte, label in RESPOSTA_LABEL:
        if escore >= corte:
            return label, round(escore, 2)
    return "lenta", round(escore, 2)


# ---------------------------------------------------------------------------
# 5. Build
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class HidrologiaResult:
    rows: list[dict[str, Any]]
    resumo: dict[str, Any]
    regioes: list[dict[str, Any]]
    limites: list[str]


def _carregar_construida() -> dict[int, float]:
    if not CONSTRUIDA_PARQUET.exists():
        return {}
    d = pd.read_parquet(CONSTRUIDA_PARQUET).dropna(subset=["frac_construida"])
    return {int(r.cod_mun): float(r.frac_construida) for r in d.itertuples()}


def build(centroides: dict[int, tuple[float, float]] | None = None) -> HidrologiaResult:
    if not CRUZADO_PARQUET.exists():
        raise FileNotFoundError(
            f"{CRUZADO_PARQUET} ausente — rode `python -m src.ingest.ibge_bdia`"
        )
    cruzado = pd.read_parquet(CRUZADO_PARQUET)
    construida = _carregar_construida()
    relevo = _relevo_medido()
    chuvas = chuvas_de_projeto()
    estacoes = pd.read_parquet(GHCN_ESTACOES)
    estacoes = estacoes[estacoes.station_id.isin(chuvas)]

    if centroides is None:
        from src.risk.recursos import _centroides

        centroides = _centroides()

    avisos: dict[str, int] = {"sem_grupo": 0, "cobertura_suposta": 0, "mosaico": 0}
    linhas: list[dict[str, Any]] = []

    for cod, g in cruzado.groupby("cod_mun"):
        cod = int(cod)
        area_km2 = float(g.km2.sum())
        if area_km2 <= 0:
            continue

        cn_num, cn_den = 0.0, 0.0
        por_grupo: dict[str, float] = {}
        por_cobertura: dict[str, float] = {}
        for r in g.itertuples():
            grupo = grupo_hidrologico(r.pedo_ordem, r.pedo_legenda_2, r.pedo_textura)
            cob = classe_cobertura(r.vege_legenda_2, r.vege_nm_uantr)
            if grupo is None and cob not in ("agua", "urbano"):
                avisos["sem_grupo"] += 1
            if cob == "agropecuaria":
                avisos["mosaico"] += 1
            if not (r.vege_legenda_2 or r.vege_nm_uantr):
                avisos["cobertura_suposta"] += 1
            cn = cn_de(grupo, cob)
            if cn is None:
                continue
            cn_num += cn * r.km2
            cn_den += r.km2
            if grupo:
                por_grupo[grupo] = por_grupo.get(grupo, 0.0) + r.km2
            por_cobertura[cob] = por_cobertura.get(cob, 0.0) + r.km2

        if cn_den <= 0:
            continue

        cn_solo = cn_num / cn_den
        # A superficie construida MEDIDA entra por cima, e nao dentro do
        # rotulo urbano do IBGE: o rotulo delimita a mancha urbana inteira
        # (quintal, praca e rua), o GHSL mede o telhado e o pavimento dentro
        # dela. Compor os dois assim evita contar o asfalto duas vezes e evita
        # tratar a cidade inteira como impermeavel, que e o erro comum.
        f_imp = construida.get(cod)
        cn2 = cn_solo if f_imp is None else (f_imp * CN_IMPERMEAVEL + (1 - f_imp) * cn_solo)
        cn3 = cn_umidade_alta(cn2)

        est = None
        if cod in centroides and len(estacoes):
            lon, lat = centroides[cod]
            d = estacoes.assign(
                km=[_km(lat, lon, r.lat, r.lon) for r in estacoes.itertuples()]
            ).nsmallest(1, "km").iloc[0]
            est = (str(d.station_id), float(d.km))

        eventos = []
        if est is not None:
            cp = chuvas[est[0]]
            for tr in TR_ANOS:
                p = cp.por_tr[tr]
                q2 = escoamento_mm(p, cn2)
                q3 = escoamento_mm(p, cn3)
                eventos.append({
                    "tr_anos": tr,
                    "p24h_mm": p,
                    "escoamento_mm": round(q2, 1),
                    "escoamento_mm_solo_umido": round(q3, 1),
                    "coef_escoamento": round(q2 / p, 3) if p > 0 else None,
                    # Volume no municipio inteiro. Serve de ordem de grandeza
                    # comparavel — nao e o volume que chega a lugar nenhum,
                    # porque nada aqui roteia agua.
                    "volume_hm3": round(q2 * area_km2 / 1000.0, 2),
                })

        decliv = relevo.get(cod)
        rotulo, escore = _resposta_ordinal(g, decliv)
        linhas.append({
            "cod_mun": cod,
            "municipio": g.municipio.iloc[0],
            "area_km2": round(area_km2, 1),
            "cn2": round(cn2, 1),
            "cn3_solo_umido": round(cn3, 1),
            "cn_solo_sem_impermeavel": round(cn_solo, 1),
            "frac_construida": f_imp,
            "s_mm": round(25400.0 / cn2 - 254.0, 1),
            "grupos_hidrologicos": {k: round(v / area_km2, 4) for k, v in sorted(por_grupo.items())},
            "cobertura": {
                k: round(v / area_km2, 4)
                for k, v in sorted(por_cobertura.items(), key=lambda x: -x[1])
            },
            "resposta": rotulo,
            "resposta_escore": escore,
            "declividade_media_pct": decliv,
            "relevo_medido": decliv is not None,
            "estacao_chuva": None if est is None else {
                "station_id": est[0],
                "nome": chuvas[est[0]].estacao,
                "km": round(est[1], 1),
                "anos": chuvas[est[0]].anos,
            },
            "eventos": eventos,
            "unidade_geomorfologica": (
                g.groupby("geom_nm_unidade").km2.sum().idxmax()
                if g.geom_nm_unidade.notna().any() else None
            ),
        })

    rows = sorted(linhas, key=lambda r: -r["cn2"])

    # Agregacao por unidade de relevo: a bacia nao respeita divisa municipal, e
    # a unidade geomorfologica e a regiao natural mais proxima disso que o dado
    # sustenta. Um planalto inteiro com CN alto e um problema de bacia; um
    # municipio isolado com CN alto e um problema local.
    por_regiao: dict[str, dict[str, Any]] = {}
    for r in rows:
        u = r["unidade_geomorfologica"]
        if not u:
            continue
        d = por_regiao.setdefault(u, {"unidade": u, "n_municipios": 0, "area_km2": 0.0,
                                      "cn_num": 0.0, "municipios_cn_alto": []})
        d["n_municipios"] += 1
        d["area_km2"] += r["area_km2"]
        d["cn_num"] += r["cn2"] * r["area_km2"]

    cn_p90 = float(np.quantile([r["cn2"] for r in rows], 0.90)) if rows else 0.0
    for r in rows:
        u = r["unidade_geomorfologica"]
        if u and r["cn2"] >= cn_p90:
            por_regiao[u]["municipios_cn_alto"].append(r["municipio"])
    regioes = []
    for d in por_regiao.values():
        regioes.append({
            "unidade": d["unidade"],
            "n_municipios": d["n_municipios"],
            "area_km2": round(d["area_km2"], 1),
            "cn2_medio": round(d["cn_num"] / d["area_km2"], 1) if d["area_km2"] else None,
            "municipios_cn_alto": sorted(d["municipios_cn_alto"])[:12],
        })
    regioes.sort(key=lambda d: -(d["cn2_medio"] or 0))

    resumo = {
        "version": VERSION,
        "n_municipios": len(rows),
        "razao_ia": RAZAO_IA,
        "tr_anos": list(TR_ANOS),
        "cn2_mediano": round(float(np.median([r["cn2"] for r in rows])), 1) if rows else None,
        "cn2_p90": round(cn_p90, 1),
        "n_estacoes_chuva": len(chuvas),
        "n_com_declividade_medida": int(sum(1 for r in rows if r["relevo_medido"])),
        "declividade_media_rs_pct": (
            round(float(np.mean([r["declividade_media_pct"] for r in rows
                                 if r["declividade_media_pct"] is not None])), 2)
            if relevo else None
        ),
        "avisos": avisos,
    }

    limites = [
        "Lamina escoada NAO e vazao, cota nem area inundada. Entre uma coisa e "
        "outra ha caminho, tempo, rede de drenagem e o nivel do corpo receptor "
        "— e no RS o receptor costuma ser laguna governada por vento.",
        "Curve Number e metodo de evento calibrado em bacias agricolas "
        "americanas nos anos 1950. A relacao Ia=0,2S e convencao de manual, nao "
        "medida; o payload carrega a razao usada para que trocar seja visivel.",
        "O grupo hidrologico e traducao da ordem do SiBCS, nao ensaio de "
        "infiltracao. Nenhum ponto do estado teve condutividade medida aqui.",
        "O mosaico 'Agropecuaria' do IBGE cobre cerca de tres quartos do estado "
        "e mistura lavoura com pasto; o CN dessa classe e a media das duas, e e "
        "a maior incerteza isolada do modelo.",
        "A chuva de projeto vem da estacao GHCN mais proxima do centroide, por "
        "Gumbel sobre maximos anuais. Municipio grande ou distante da estacao "
        "herda uma chuva que nao e a dele; a distancia viaja no payload.",
        "A declividade vem do Copernicus DEM de 90 m, que e modelo de SUPERFICIE: "
        "mede topo de dossel e telhado, e em area florestada sai contaminada pela "
        "borda da mata. O comprimento de rampa continua suposto.",
        "A cartografia de solo e cobertura e 1:250.000: o resultado ordena municipios, nao "
        "dimensiona obra. Nenhum numero daqui substitui estudo hidrologico "
        "local.",
        "Sem serie fluviometrica ingerida, nada disto foi confrontado com vazao "
        "observada. E tabela aplicada, nao modelo calibrado.",
    ]
    return HidrologiaResult(rows=rows, resumo=resumo, regioes=regioes, limites=limites)
