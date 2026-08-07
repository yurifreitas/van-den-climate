"""Plano de acao preventiva — o que fazer, onde, antes de quando.

O que este modulo faz
=====================

Todas as camadas anteriores respondem perguntas de diagnostico: onde o risco e
maior, onde a agua ja esteve, quem ficou sem hospital, quem nao executou o
plano. Nenhuma delas diz o que FAZER. Este modulo faz a ultima traducao: de
lacuna declarada para acao nomeada, municipio a municipio.

A regra que governa tudo aqui
=============================

**Toda acao tem de sair de um dado declarado, nunca de inferencia.** Cada item
gerado carrega `evidencia` (o campo exato que o disparou) e `fonte` (a base).
Se um gatilho nao encontra o campo, a acao nao aparece — nao existe acao
"provavelmente necessaria" nesta lista.

Isso mantem o plano falsificavel: qualquer prefeitura pode apontar a linha e
dizer "isto mudou desde 2024", e a correcao e uma reingestao, nao uma
discussao.

O que este plano NAO e
======================

1. Nao e plano de engenharia. Nao ha projeto, custo, prazo nem
   dimensionamento. "Implantar canal de alerta" e a identificacao de uma
   lacuna, nao um termo de referencia.
2. Nao e priorizacao por custo-beneficio. Ordena por risco e por lacuna, nao
   por retorno — nao existe base publica de custo de acao preventiva por
   municipio para calcular retorno.
3. O campo `esforco` e ESCOLHA EDITORIAL declarada, nao medicao. Serve para
   separar o que cabe numa primavera do que exige ciclo orcamentario, e esta
   escrito por extenso em ACOES para que discordar seja facil.
4. Nao substitui o Plano Municipal de Reducao de Riscos nem o plano de
   contingencia da Defesa Civil. Aponta a ausencia deles.

Horizonte
=========

`imediato`   cabe antes de OND/2026: e ato administrativo, contrato ou
             treinamento. Nao depende de obra.
`estrutural` exige ciclo orcamentario, projeto ou obra. E o que se planeja
             para 2027 e adiante — e, por nao depender de previsao ENSO, e
             exatamente o que se pode decidir hoje (ver ADR-026).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from src.risk import municipal, resposta

VERSION = "plano-v1"

# Fracao de memoria hidrica a partir da qual o mapeamento de planicie entra no
# plano. 5% do territorio com precedente de agua e um piso deliberadamente
# baixo: o custo de mapear e de gabinete, e o custo de nao mapear apareceu em
# 2024.
LIMIAR_MEMORIA = 0.05

# Autonomia logistica abaixo disto vira acao. 0,7 e o ponto em que o municipio
# declarou falha em pelo menos uma capacidade critica testada.
LIMIAR_AUTONOMIA = 0.70

# Distancia a partir da qual a ausencia de unidade de urgencia vira acao de
# pactuacao formal, e nao apenas um fato geografico.
LIMIAR_KM_REFERENCIA = 25.0


@dataclass(frozen=True)
class Acao:
    """Uma acao possivel e o gatilho que a torna necessaria.

    `gatilho` recebe (linha do indice municipal, linha da camada de resposta)
    e devolve a evidencia textual quando dispara, ou None quando nao se aplica.
    """

    id: str
    titulo: str
    horizonte: str            # imediato | estrutural
    esforco: str              # baixo | medio | alto — editorial, ver docstring
    fonte: str
    gatilho: Callable[[dict, dict | None], str | None]
    detalhe: str = ""


def _det(linha: dict, caminho: str) -> Any:
    """Acesso seguro a `componentes.<x>.detalhe.<y>`."""
    c = linha.get("componentes", {}).get(caminho, {})
    return c.get("detalhe", {}) if isinstance(c, dict) else {}


# ---------------------------------------------------------------------------
# Catalogo de acoes
# ---------------------------------------------------------------------------
def _sem_plano(m: dict, _r: dict | None) -> str | None:
    d = _det(m, "deficit_prevencao")
    if d.get("plano_contingencia") is False:
        return "MUNIC 2024: municipio declarou NAO possuir plano de contingencia"
    return None


def _plano_nao_executado(m: dict, _r: dict | None) -> str | None:
    d = _det(m, "deficit_prevencao")
    if d.get("plano_contingencia") is True and d.get("plano_executado") is False:
        motivos = [l for l in (d.get("lacunas") or []) if l.startswith("falta")]
        sufixo = f" — motivos declarados: {', '.join(motivos)}" if motivos else ""
        return f"MUNIC 2024: plano existia e NAO foi executado{sufixo}"
    return None


def _sem_alerta(m: dict, _r: dict | None) -> str | None:
    d = _det(m, "deficit_prevencao")
    if d.get("alerta_emitido") is False:
        return "MUNIC 2024: nenhum alerta foi emitido a populacao durante o evento"
    return None


def _alerta_sem_alcance(m: dict, _r: dict | None) -> str | None:
    d = _det(m, "deficit_prevencao")
    for l in d.get("lacunas") or []:
        if "alcancou apenas" in l or "canal automatico" in l:
            return f"MUNIC 2024: {l}"
    return None


def _sem_psicologico(_m: dict, r: dict | None) -> str | None:
    if r and r["resposta"]["apoio_psicologico"] is False:
        return "MUNIC 2024: municipio declarou NAO ter oferecido apoio psicologico as vitimas"
    return None


def _sem_referencia_saude(_m: dict, r: dict | None) -> str | None:
    if not r:
        return None
    cap = r["capacidade"]
    km = cap["km_ate_unidade_mais_proxima"]
    if cap["total"] == 0 and km is not None and km >= LIMIAR_KM_REFERENCIA:
        return f"CNES: nenhum hospital ou pronto-socorro no municipio; o mais proximo esta a {km:.0f} km"
    return None


def _saude_vulneravel(_m: dict, r: dict | None) -> str | None:
    if not r:
        return None
    impactos = r["saude"]["impactos"]
    criticos = [i for i in impactos if "suspens" in i or "remanejamento" in i]
    if criticos:
        return f"MUNIC 2024: {'; '.join(criticos)}"
    return None


def _autonomia_baixa(_m: dict, r: dict | None) -> str | None:
    if not r:
        return None
    a = r["autonomia_logistica"]
    if a["indice"] is not None and a["indice"] < LIMIAR_AUTONOMIA and a["n_aplicaveis"] >= 2:
        piores = [i["rotulo"] for i in a["itens"] if i["valor"] is not None and i["valor"] <= 0.55]
        sufixo = f" — pior em: {', '.join(piores[:3])}" if piores else ""
        return f"MUNIC 2024: autonomia logistica {a['indice']:.2f} em {a['n_aplicaveis']} escalas{sufixo}"
    return None


def _mapear_planicie(m: dict, _r: dict | None) -> str | None:
    ag = m.get("aguas")
    if not ag or ag.get("memoria_hidrica_frac") is None:
        return None
    frac = ag["memoria_hidrica_frac"]
    if frac >= LIMIAR_MEMORIA:
        return (
            f"JRC 1984-2021: {frac * 100:.1f}% do territorio ja foi agua e hoje nao e "
            f"({ag['memoria_hidrica_km2']:.0f} km²)"
        )
    return None


def _grupos_expostos(_m: dict, r: dict | None) -> str | None:
    if not r:
        return None
    grupos = r["vulneraveis"]["grupos"]
    prioritarios = [
        g for g in grupos
        if any(k in g for k in ("favela", "situacao de rua", "tradicionais", "deficiencia", "cronicas"))
    ]
    if prioritarios:
        return f"MUNIC 2024: grupos atingidos que exigem evacuacao assistida — {'; '.join(prioritarios)}"
    return None


ACOES: list[Acao] = [
    Acao(
        id="escrever_plano",
        titulo="Elaborar plano de contingencia de protecao e defesa civil",
        horizonte="imediato",
        esforco="medio",
        fonte="ibge_munic_rs",
        gatilho=_sem_plano,
        detalhe="E a lacuna mais grave e a mais barata de fechar: e documento e exercicio, nao obra.",
    ),
    Acao(
        id="destravar_plano",
        titulo="Destravar a execucao do plano existente",
        horizonte="imediato",
        esforco="baixo",
        fonte="ibge_munic_rs",
        gatilho=_plano_nao_executado,
        detalhe="O plano existe. O que faltou esta declarado pelo proprio municipio — atacar o motivo nomeado.",
    ),
    Acao(
        id="implantar_alerta",
        titulo="Implantar emissao de alerta a populacao",
        horizonte="imediato",
        esforco="baixo",
        fonte="ibge_munic_rs",
        gatilho=_sem_alerta,
        detalhe="Sem alerta emitido, todo o resto do plano chega depois da agua.",
    ),
    Acao(
        id="ampliar_alcance",
        titulo="Ampliar alcance do alerta (canal automatico: SMS, aplicativo, sirene)",
        horizonte="imediato",
        esforco="baixo",
        fonte="ibge_munic_rs",
        gatilho=_alerta_sem_alcance,
        detalhe="Alerta que alcanca metade da populacao protege metade da populacao.",
    ),
    Acao(
        id="apoio_psicologico",
        titulo="Estruturar oferta de apoio psicologico pos-evento",
        horizonte="imediato",
        esforco="medio",
        fonte="ibge_munic_rs",
        gatilho=_sem_psicologico,
        detalhe="A camada de recuperacao mais frequentemente ausente no RS em 2024.",
    ),
    Acao(
        id="evacuacao_assistida",
        titulo="Protocolo de evacuacao assistida para grupos declarados",
        horizonte="imediato",
        esforco="medio",
        fonte="ibge_munic_rs",
        gatilho=_grupos_expostos,
        detalhe="Populacao em area de risco, em situacao de rua, com deficiencia ou doenca cronica "
                "nao evacua sozinha — precisa de protocolo nominal, nao de aviso geral.",
    ),
    Acao(
        id="autonomia",
        titulo="Revisar estoque, fornecimento e cooperacao da primeira resposta",
        horizonte="imediato",
        esforco="medio",
        fonte="ibge_munic_rs",
        gatilho=_autonomia_baixa,
        detalhe="O municipio foi testado em 2024 e declarou onde nao aguentou.",
    ),
    Acao(
        id="referencia_saude",
        titulo="Pactuar referencia de urgencia e rota alternativa de acesso",
        horizonte="estrutural",
        esforco="alto",
        fonte="cnes_rs",
        gatilho=_sem_referencia_saude,
        detalhe="Distancia em linha reta; por estrada e maior, e em cheia pode nao existir. "
                "A pactuacao e administrativa, a rota alternativa e obra.",
    ),
    Acao(
        id="continuidade_saude",
        titulo="Plano de continuidade dos servicos de saude",
        horizonte="estrutural",
        esforco="medio",
        fonte="ibge_munic_rs",
        gatilho=_saude_vulneravel,
        detalhe="Atendimento suspenso ou paciente remanejado em 2024 indica ponto unico de falha.",
    ),
    Acao(
        id="mapear_planicie",
        titulo="Mapear planicie reocupavel e revisar uso do solo",
        horizonte="estrutural",
        esforco="alto",
        fonte="jrc_gsw",
        gatilho=_mapear_planicie,
        detalhe="Terreno com precedente de agua no periodo 1984-2021. Mapear e de gabinete; "
                "o que decorre disso (zoneamento, realocacao) nao e.",
    ),
]


@dataclass
class PlanoMunicipio:
    cod_mun: int
    municipio: str
    score: float | None
    level: str | None
    populacao: int | None
    acoes: list[dict[str, Any]] = field(default_factory=list)

    @property
    def n_imediatas(self) -> int:
        return sum(1 for a in self.acoes if a["horizonte"] == "imediato")


def build(cenario: str = "atual", oni: float | None = None) -> dict[str, Any]:
    """Plano completo: acoes por municipio e o agregado estadual."""
    tabela = municipal.build_table(oni, cenario)
    resp = {r["cod_mun"]: r for r in resposta.build_table().rows}

    planos: list[PlanoMunicipio] = []
    for linha in tabela.rows:
        r = resp.get(linha["cod_mun"])
        acoes = []
        for acao in ACOES:
            evidencia = acao.gatilho(linha, r)
            if evidencia is None:
                continue
            acoes.append({
                "id": acao.id,
                "titulo": acao.titulo,
                "horizonte": acao.horizonte,
                "esforco": acao.esforco,
                "fonte": acao.fonte,
                "detalhe": acao.detalhe,
                "evidencia": evidencia,
                "basis": "measured",
            })
        planos.append(PlanoMunicipio(
            cod_mun=linha["cod_mun"],
            municipio=linha["municipio"],
            score=linha["score"],
            level=linha["level"],
            populacao=linha["populacao"],
            acoes=acoes,
        ))

    # Ordena por risco; empate por numero de acoes imediatas pendentes. Um
    # municipio com mais lacunas fechaveis nesta primavera sobe: e onde a
    # mesma quantidade de esforco compra mais reducao de risco.
    planos.sort(key=lambda p: (p.score is None, -(p.score or 0.0), -p.n_imediatas, p.cod_mun))

    por_acao: dict[str, dict[str, Any]] = {}
    for acao in ACOES:
        atingidos = [p for p in planos if any(a["id"] == acao.id for a in p.acoes)]
        pop = sum(p.populacao or 0 for p in atingidos)
        por_acao[acao.id] = {
            "id": acao.id,
            "titulo": acao.titulo,
            "horizonte": acao.horizonte,
            "esforco": acao.esforco,
            "fonte": acao.fonte,
            "detalhe": acao.detalhe,
            "n_municipios": len(atingidos),
            "populacao_coberta": pop,
            "exemplos": [p.municipio for p in atingidos[:5]],
        }

    com_acao = [p for p in planos if p.acoes]
    return {
        "version": VERSION,
        "cenario": tabela.cenario,
        "n_municipios": len(planos),
        "n_com_acao": len(com_acao),
        "n_acoes_total": sum(len(p.acoes) for p in planos),
        "n_imediatas_total": sum(p.n_imediatas for p in planos),
        "por_acao": list(por_acao.values()),
        "municipios": [
            {
                "cod_mun": p.cod_mun,
                "municipio": p.municipio,
                "score": p.score,
                "level": p.level,
                "populacao": p.populacao,
                "n_acoes": len(p.acoes),
                "n_imediatas": p.n_imediatas,
                "acoes": p.acoes,
            }
            for p in planos
        ],
        "regras": {
            "limiar_memoria_hidrica": LIMIAR_MEMORIA,
            "limiar_autonomia": LIMIAR_AUTONOMIA,
            "limiar_km_referencia": LIMIAR_KM_REFERENCIA,
            "ordenacao": "risco; empate por numero de acoes imediatas pendentes",
        },
        "limites": [
            "Toda acao sai de dado DECLARADO pelo municipio ao IBGE em 2024 ou de cadastro "
            "(CNES, JRC). Nao ha acao inferida — se o campo falta, a acao nao aparece.",
            "Nao e plano de engenharia: sem projeto, custo, prazo ou dimensionamento.",
            "Nao e priorizacao por custo-beneficio — nao existe base publica de custo de acao "
            "preventiva por municipio.",
            "`esforco` e escolha editorial declarada, nao medicao.",
            "Retrato de 2024: um municipio que fechou a lacuna desde entao continua listado ate "
            "a proxima edicao do MUNIC.",
            "Nao substitui o Plano Municipal de Reducao de Riscos nem o plano de contingencia da "
            "Defesa Civil — aponta a ausencia deles.",
        ],
    }
