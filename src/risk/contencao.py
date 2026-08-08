"""Estrategias de contencao — a obra certa para o mecanismo certo.

A pergunta
==========

Dois municipios com o mesmo indice de risco podem precisar de obras OPOSTAS.
O que decide nao e a magnitude do risco: e o mecanismo. Este modulo cruza

    regime de cheia   lagunar | fluvial com remanso | fluvial  (ANA)
    perigo geotecnico encosta e talude                          (MUNIC 2024)
    memoria hidrica   onde ja foi agua e deixou de ser           (JRC)
    impermeabilizacao superficie construida                      (GHSL)

e devolve, para cada municipio, as estrategias cabiveis — cada uma com a
alternativa CONVENCIONAL e a BASEADA NA NATUREZA lado a lado.

Por que as duas juntas, e nao a "melhor"
========================================

Solucao baseada na natureza nao e superior por natureza: e diferente. Varzea
restaurada absorve cheia frequente e falha em cheia de tempo de retorno alto;
dique aguenta o extremo de projeto e falha catastroficamente acima dele —
e transfere o problema para o vizinho de jusante. Restauracao exige terra e
decada; dique exige orcamento e manutencao perpetua.

Apresentar so uma das duas seria escolher pelo gestor com base em preferencia,
nao em dado. Este modulo apresenta o PAR e nomeia o custo de cada lado. A
escolha e de quem tem o territorio.

Onde a base natural e mais forte que a convencional, isso esta dito no campo
`quando_natureza_ganha` — e o argumento e sempre fisico, nunca ideologico.

A REGRA QUE MANTEM ISTO HONESTO
===============================

Toda estrategia so aparece onde o GATILHO fisico existe no dado. Nao ha
recomendacao generica: "restaurar varzea" so surge onde ha memoria hidrica
medida; "bioengenharia de encosta" so onde houve deslizamento declarado.

E nenhuma delas e projeto. Sao FAMILIAS de intervencao, com o que cada uma
exige. Dimensionamento, custo e prazo exigem estudo que esta fora desta
central — a mesma fronteira de todo o resto do projeto.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
INTERIM = REPO_ROOT / "data" / "interim"

BACIAS_PARQUET = INTERIM / "ana_bacias.parquet"
CONSTRUIDA_PARQUET = INTERIM / "ghsl_built_rs.parquet"

VERSION = "contencao-v1"

# Fracao de area construida a partir da qual a drenagem urbana vira o problema
# dominante.
#
# Este limite era 0,08 absoluto, escrito antes de existir o dado. Com o GHSL
# ingerido ele se revelou errado por um motivo que vale registrar, porque e o
# tipo de erro que passa despercebido: a literatura classica de hidrologia
# urbana (modelo de cobertura impermeavel, Schueler) situa a degradacao entre
# 10% e 25% — mas esses numeros sao de **bacia**, e o que temos e fracao de
# **municipio**. Sao denominadores diferentes por uma ordem de grandeza: um
# municipio inclui toda a area rural, e a mancha urbana onde a chuva de fato
# cai sobre concreto pode passar de 60% enquanto o municipio inteiro marca 5%.
# Aplicar o limite de bacia sobre a fracao municipal e erro de categoria, e no
# RS ele deixava passar 13 municipios de 497.
#
# A leitura que o dado sustenta e ordinal (ver o modulo de ingestao). Entao o
# corte e o **percentil 90 do proprio estado**, calculado a cada build e
# declarado no payload: "esta entre os 10% mais impermeabilizados do RS" e uma
# afirmacao verificavel; "passou de 8%" nao era.
PERCENTIL_IMPERMEAVEL = 0.90

# Piso absoluto sob o percentil. Sem ele, um estado inteiro pouco urbanizado
# ainda teria 10% dos seus municipios rotulados como problema de drenagem —
# percentil sempre acha um topo, mesmo quando nao ha nada la.
PISO_IMPERMEAVEL = 0.01


@dataclass(frozen=True)
class Estrategia:
    id: str
    titulo: str
    mecanismo: str          # qual fisica ela ataca
    convencional: str
    natureza: str
    quando_natureza_ganha: str
    limite: str             # onde a solucao natural NAO resolve
    gatilho: Callable[[dict], str | None]


# ---------------------------------------------------------------------------
# Gatilhos — cada um le um campo especifico e devolve a evidencia
# ---------------------------------------------------------------------------
def _lagunar(ctx: dict) -> str | None:
    if ctx.get("regime") == "lagunar":
        return (
            "ANA: bacia lagunar (Guaiba/Patos/Mirim/costeiras) — o nivel e governado por "
            "vento, e a drenagem por gravidade falha quando a laguna sobe"
        )
    return None


def _remanso(ctx: dict) -> str | None:
    if ctx.get("regime") == "fluvial_com_remanso":
        return (
            "ANA: bacia fluvial com remanso da laguna — cheia rapida propria somada ao "
            "represamento do trecho baixo quando o Guaiba esta alto"
        )
    return None


def _planicie(ctx: dict) -> str | None:
    frac = ctx.get("memoria_hidrica_frac")
    if frac is not None and frac >= 0.05:
        return (
            f"JRC 1984-2021: {frac * 100:.1f}% do territorio ja foi agua e hoje nao e — "
            "planicie com precedente fisico de reocupacao"
        )
    return None


def _encosta(ctx: dict) -> str | None:
    oc = ctx.get("geotecnico_ocorrencias") or []
    graves = [o for o in oc if "deslizamento" in o or "corrida" in o]
    if graves:
        return f"MUNIC 2024: {'; '.join(graves)}"
    return None


def _urbano(ctx: dict) -> str | None:
    frac = ctx.get("frac_construida")
    limiar = ctx.get("limiar_impermeavel")
    if frac is None or limiar is None or frac < limiar:
        return None
    return (
        f"GHSL 2025: {frac * 100:.1f}% da area do municipio e superficie construida, "
        f"acima do percentil {PERCENTIL_IMPERMEAVEL:.0%} do RS ({limiar * 100:.1f}%) — "
        "a chuva que cai ali nao infiltra"
    )


def _alagamento(ctx: dict) -> str | None:
    if ctx.get("teve_alagamento") is True:
        return "MUNIC 2024: alagamento por saturacao da drenagem urbana declarado"
    return None


# ---------------------------------------------------------------------------
# Catalogo de estrategias
# ---------------------------------------------------------------------------
ESTRATEGIAS: list[Estrategia] = [
    Estrategia(
        id="controle_lagunar",
        titulo="Controle de nivel em sistema lagunar",
        mecanismo="empilhamento por vento e bloqueio da saida — nao chuva local",
        convencional=(
            "Dique com comporta e casa de bombas: a unica forma de drenar contra nivel alto "
            "quando a gravidade nao funciona. Exige manutencao perpetua e energia de reserva — "
            "foi exatamente onde Porto Alegre falhou em 2024."
        ),
        natureza=(
            "Faixa de banhado e varzea na margem, que amortece o empilhamento e dissipa energia "
            "de onda antes da linha construida. Nao substitui a comporta: reduz a carga sobre ela "
            "e da tempo."
        ),
        quando_natureza_ganha=(
            "Onde ainda ha margem nao ocupada. Banhado marginal nao tem modo de falha "
            "catastrofico e nao precisa de energia — um dique sem bomba e pior que nenhum dique."
        ),
        limite=(
            "Nao resolve nivel: contra vento de sul sustentado, so bombeamento tira agua. "
            "A solucao natural aqui e complemento, nunca substituto."
        ),
        gatilho=_lagunar,
    ),
    Estrategia(
        id="reconexao_varzea",
        titulo="Reconexao de varzea e area de amortecimento",
        mecanismo="cheia fluvial rapida com remanso no trecho baixo",
        convencional=(
            "Canalizacao e retificacao: acelera a passagem no trecho tratado e TRANSFERE o pico "
            "para jusante. Barragem de amortecimento resolve de verdade, mas e obra de decada."
        ),
        natureza=(
            "Devolver ao rio a planicie que ele perdeu: recuo de dique, area de inundacao "
            "controlada, mata ciliar. Corta o pico armazenando volume em vez de acelera-lo."
        ),
        quando_natureza_ganha=(
            "Quase sempre em bacia com remanso: acelerar agua rio abaixo nao ajuda quando a "
            "foz esta represada pela laguna — a agua so chega mais rapido num lugar que nao "
            "aceita. Armazenar a montante e o unico caminho que a fisica permite."
        ),
        limite=(
            "Exige terra, e terra de varzea e a mais produtiva da bacia. Sem instrumento de "
            "compensacao ao produtor, e proposta que nao sai do papel."
        ),
        gatilho=_remanso,
    ),
    Estrategia(
        id="restaurar_planicie",
        titulo="Restauracao de planicie e banhado suprimido",
        mecanismo="terreno com precedente medido de agua, hoje seco no mapa oficial",
        convencional=(
            "Aterro e drenagem para manter o uso atual, com bombeamento quando enche. "
            "Custo recorrente e cresce a cada evento."
        ),
        natureza=(
            "Reumidificar banhado drenado e recompor a lamina sazonal. O terreno JA foi agua "
            "entre 1984 e 2021 — a restauracao trabalha a favor da hidrologia, nao contra."
        ),
        quando_natureza_ganha=(
            "Onde a memoria hidrica e alta: restaurar o que a paisagem faz sozinha custa menos "
            "que manter permanentemente um regime que ela nao sustenta."
        ),
        limite=(
            "Nao e reversivel de graca: ha uso instalado sobre esse terreno hoje. Exige "
            "zoneamento e, em area urbana, realocacao — que e a intervencao mais cara e lenta "
            "que existe."
        ),
        gatilho=_planicie,
    ),
    Estrategia(
        id="estabilizar_encosta",
        titulo="Estabilizacao de encosta",
        mecanismo="talude saturado — deslizamento e corrida de massa",
        convencional=(
            "Contencao em concreto, cortina atirantada, muro de arrimo. Resolve o talude "
            "tratado, e caro por metro e nao escala para uma encosta inteira."
        ),
        natureza=(
            "Bioengenharia de solos: retaludamento suave, drenagem superficial, revegetacao com "
            "especies de raiz profunda, paliçada viva. Raiz costura o solo e a copa reduz o "
            "impacto da gota."
        ),
        quando_natureza_ganha=(
            "Em encosta rural e periurbana, onde a area e grande e nao ha estrutura a proteger "
            "imediatamente abaixo. Custa uma fracao do concreto e cobre area, nao ponto."
        ),
        limite=(
            "Leva estacoes para ganhar resistencia e nao segura escorregamento profundo nem "
            "talude sob edificacao. Onde ha casa no pe da encosta, a resposta e concreto ou "
            "realocacao — nao vegetacao."
        ),
        gatilho=_encosta,
    ),
    Estrategia(
        id="drenagem_urbana",
        titulo="Drenagem urbana e superficie permeavel",
        mecanismo="chuva sobre superficie impermeavel — escoamento sem infiltracao",
        convencional=(
            "Ampliar galeria e bueiro. Move o problema para o exutorio mais rapido, e em bacia "
            "lagunar o exutorio pode estar represado justamente quando mais se precisa dele."
        ),
        natureza=(
            "Infraestrutura verde: jardim de chuva, biovaleta, pavimento permeavel, telhado "
            "verde, microreservatorio de lote. Infiltra e retarda na origem, distribuido pela "
            "cidade em vez de concentrado num tubo."
        ),
        quando_natureza_ganha=(
            "Em chuva frequente, que e a que mais alaga e mais custa no acumulado. E pode ser "
            "implantada por partes, sem obra unica — cada quadra tratada ja reduz."
        ),
        limite=(
            "Satura em evento extremo: contra chuva de tempo de retorno alto, o volume excede "
            "qualquer infiltracao. Nao dispensa a rede — reduz a carga sobre ela."
        ),
        gatilho=_urbano,
    ),
    Estrategia(
        id="retencao_alagamento",
        titulo="Retencao e amortecimento de alagamento",
        mecanismo="drenagem urbana saturada, declarada no evento",
        convencional="Reservatorio de detencao em concreto (piscinao). Eficaz e pontual.",
        natureza=(
            "Parque alagavel e praca inundavel: area publica que funciona como lazer no seco e "
            "como reservatorio na cheia. Mesmo volume, uso duplo."
        ),
        quando_natureza_ganha=(
            "Onde ha area publica disponivel: entrega volume de amortecimento E area verde pelo "
            "custo de uma obra so, com manutencao mais barata que estrutura enterrada."
        ),
        limite=(
            "Precisa de area na cota certa, que em cidade consolidada e justamente o que falta. "
            "E exige protocolo de esvaziamento e interdicao — parque alagavel sem aviso e risco."
        ),
        gatilho=_alagamento,
    ),
]


def carregar_construida() -> dict[int, float]:
    """Fracao construida por municipio, do GHSL. Ausente devolve vazio.

    Ausente NAO e erro: a estrategia de drenagem urbana simplesmente nao
    dispara, e o payload declara a cobertura em `n_com_frac_construida`. O que
    seria erro e tratar ausencia como zero e afirmar que nao ha cidade ali.
    """
    if not CONSTRUIDA_PARQUET.exists():
        return {}
    d = pd.read_parquet(CONSTRUIDA_PARQUET).dropna(subset=["frac_construida"])
    return {int(r.cod_mun): float(r.frac_construida) for r in d.itertuples()}


def _limiar_impermeavel(construida: dict[int, float]) -> float | None:
    """Percentil do proprio estado, com piso. Sem dado, nao ha limite."""
    if len(construida) < 30:
        return None
    import numpy as np

    p = float(np.quantile(list(construida.values()), PERCENTIL_IMPERMEAVEL))
    return round(max(p, PISO_IMPERMEAVEL), 5)


def _contexto(cod: int, municipal_row: dict, geo_row: dict | None,
              bacia: dict | None, construida: float | None,
              limiar: float | None) -> dict[str, Any]:
    ag = municipal_row.get("aguas") or {}
    det = (municipal_row.get("componentes", {}).get("impacto", {}) or {}).get("detalhe", {}) or {}
    perigos = det.get("perigos") or []
    return {
        "cod_mun": cod,
        "regime": (bacia or {}).get("regime"),
        "bacia": (bacia or {}).get("bacia"),
        "memoria_hidrica_frac": ag.get("memoria_hidrica_frac"),
        "geotecnico_ocorrencias": (geo_row or {}).get("geotecnico", {}).get("ocorrencias"),
        "frac_construida": construida,
        "limiar_impermeavel": limiar,
        "teve_alagamento": "oc_alagamento" in perigos or "alagamento (drenagem urbana)" in perigos,
    }


def build(indice: list[dict[str, Any]], geo_rows: list[dict[str, Any]] | None = None,
          construida: dict[int, float] | None = None) -> dict[str, Any]:
    """Estrategias cabiveis por municipio, com o par convencional/natureza."""
    if not BACIAS_PARQUET.exists():
        raise FileNotFoundError(
            f"{BACIAS_PARQUET} ausente — rode `python -m src.ingest.ana_bacias`"
        )
    bac = pd.read_parquet(BACIAS_PARQUET)
    por_bacia = {int(r["cod_mun"]): {"regime": r["regime"], "bacia": r["bacia"]}
                 for _, r in bac.iterrows()}
    por_geo = {g["cod_mun"]: g for g in (geo_rows or [])}
    # `None` significa "use o GHSL do disco"; `{}` significa "sem esta camada".
    # A distincao importa: chamador de teste passa {} de proposito.
    construida = carregar_construida() if construida is None else construida
    limiar = _limiar_impermeavel(construida)

    linhas = []
    for m in indice:
        cod = m["cod_mun"]
        ctx = _contexto(cod, m, por_geo.get(cod), por_bacia.get(cod),
                        construida.get(cod), limiar)
        aplicaveis = []
        for e in ESTRATEGIAS:
            ev = e.gatilho(ctx)
            if ev is None:
                continue
            aplicaveis.append({
                "id": e.id,
                "titulo": e.titulo,
                "mecanismo": e.mecanismo,
                "evidencia": ev,
                "convencional": e.convencional,
                "natureza": e.natureza,
                "quando_natureza_ganha": e.quando_natureza_ganha,
                "limite": e.limite,
                "basis": "measured",
            })
        linhas.append({
            "cod_mun": cod,
            "municipio": m["municipio"],
            "score": m["score"],
            "level": m["level"],
            "regime": ctx["regime"],
            "bacia": ctx["bacia"],
            "frac_construida": ctx["frac_construida"],
            "estrategias": aplicaveis,
        })

    linhas.sort(key=lambda x: (x["score"] is None, -(x["score"] or 0.0), x["cod_mun"]))

    regimes = {}
    for x in linhas:
        regimes[x["regime"]] = regimes.get(x["regime"], 0) + 1
    por_estrategia = {
        e.id: {
            "titulo": e.titulo,
            "n_municipios": sum(1 for x in linhas if any(a["id"] == e.id for a in x["estrategias"])),
        }
        for e in ESTRATEGIAS
    }

    return {
        "version": VERSION,
        "n_municipios": len(linhas),
        "impermeabilizacao": {
            "n_com_frac_construida": len(construida),
            "limiar": limiar,
            "percentil": PERCENTIL_IMPERMEAVEL,
            "piso": PISO_IMPERMEAVEL,
            "basis": "measured" if construida else None,
            "nota": (
                "Fracao de MUNICIPIO, nao de bacia — proxy ordinal de "
                "impermeabilizacao. O corte e o percentil do proprio estado "
                "porque o limite de bacia da literatura nao se aplica a este "
                "denominador."
            ),
        },
        "por_regime": regimes,
        "por_estrategia": por_estrategia,
        "municipios": linhas,
        "principio": (
            "Solucao baseada na natureza nao e superior por natureza — e diferente. Varzea "
            "restaurada absorve cheia frequente e falha no extremo; dique aguenta o extremo de "
            "projeto e falha catastroficamente acima dele, transferindo o problema para jusante. "
            "As duas aparecem juntas, com o custo de cada lado nomeado. A escolha e de quem tem "
            "o territorio."
        ),
        "limites": [
            "Familias de intervencao, NAO projeto: sem dimensionamento, custo ou prazo.",
            "O regime de cheia e classificacao editorial sobre o poligono da ANA, nao campo do "
            "dado original — ver REGIME em src/ingest/ana_bacias.py.",
            "Regime atribuido pelo centroide: municipio a cavaleiro de duas bacias fica com uma.",
            "NAO ha modelo hidrodinamico: nada aqui calcula nivel, propaga onda de cheia ou "
            "estima tempo de retorno. Classifica MECANISMO, que e afirmacao qualitativa.",
            "Superficie construida do GHSL e proxy de impermeabilizacao, nao medida de "
            "coeficiente de escoamento.",
        ],
    }
