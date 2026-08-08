"""Dossie municipal — tudo o que a central sabe sobre um municipio, num lugar.

O problema que este modulo resolve
==================================

A central acumulou dez camadas: indice, memoria hidrica, resposta, recursos,
pessoal, geotecnico, regime, contencao, territorios, plano. Cada uma responde
bem a sua pergunta e mora no seu endpoint.

Um gestor municipal nao tem dez perguntas. Tem uma: **o que eu preciso saber
sobre a MINHA cidade para decidir?** E hoje isso exige visitar dez telas e
juntar na cabeca.

Este modulo faz a juncao, organizada pela ordem em que a decisao acontece:

    1. onde estou       indice, nivel, regime de cheia
    2. qual o perigo    componentes, memoria hidrica, encosta
    3. quem esta exposto  populacao, grupos, territorios tradicionais
    4. com o que conto   saude, bombeiro, ponte, quadro de pessoal
    5. o que falhou     deficit de prevencao, autonomia, saude afetada
    6. o que fazer      acoes do plano e estrategias de contencao
    7. o que nao sei    lacunas declaradas, por camada

REGRA QUE ORGANIZA O DOSSIE
===========================

Cada bloco carrega `basis` proprio e `lacunas` proprias. Um dossie que
apresenta dez camadas com selo unico apagaria a diferenca entre o que foi
medido, o que foi modelado e o que simplesmente nao existe — que e a
informacao mais importante quando a decisao e cara.

O bloco 7 nao e rodape. Um gestor que decide sem saber o que a central NAO
sabe decide pior do que se nao tivesse consultado nada.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from src.risk import aguas, geotecnico, municipal, pessoal, plano, recursos, resposta

VERSION = "dossie-v1"


@dataclass(frozen=True)
class Dossie:
    dados: dict[str, Any]


@lru_cache(maxsize=8)
def _camadas(cenario: str, oni: float | None) -> dict[str, Any]:
    """Todas as camadas do estado, montadas UMA vez por (cenario, oni).

    Sem este cache o dossie custa ~4 s por municipio, porque cada chamada
    remonta a tabela inteira do estado, o plano dos 497, o geotecnico, o
    raster dos territorios e o mapa de recursos — para depois jogar fora 496
    linhas. Nos 497 municipios do snapshot estatico isso vira mais de meia
    hora, e na API vira 4 s de espera por clique.

    O valor devolvido e COMPARTILHADO entre chamadas: `build` so le. Quem
    precisar mutar tem que copiar antes, ou o dossie de um municipio comeca a
    contaminar o do proximo.
    """
    tabela = municipal.build_table(oni, cenario)
    geo_todos = geotecnico.build().rows

    try:
        cobertura = recursos.build().por_municipio
    except FileNotFoundError:
        cobertura = {}

    try:
        import pandas as pd

        bac = pd.read_parquet(municipal.INTERIM / "ana_bacias.parquet")
        regimes = {
            int(r["cod_mun"]): {"regime": r["regime"], "bacia": r["bacia"]}
            for _, r in bac.iterrows()
        }
    except Exception:
        regimes = {}

    try:
        from src.risk import territorios as terr

        territ = terr.build().rows
    except (FileNotFoundError, ImportError):
        territ = []

    try:
        from src.risk import contencao

        construida = contencao.carregar_construida()
        limiar_imperm = contencao._limiar_impermeavel(construida)
        estrategias = {
            m["cod_mun"]: m["estrategias"]
            for m in contencao.build(tabela.rows, geo_todos)["municipios"]
        }
    except FileNotFoundError:
        construida, limiar_imperm, estrategias = {}, None, {}

    return {
        "tabela": tabela,
        "por_cod": {r["cod_mun"]: r for r in tabela.rows},
        "ranking": {
            r["cod_mun"]: i + 1
            for i, r in enumerate(tabela.rows)
            if r["score"] is not None
        },
        "n_com_score": sum(1 for r in tabela.rows if r["score"] is not None),
        "resposta": {r["cod_mun"]: r for r in resposta.build_table().rows},
        "pessoal": {p["cod_mun"]: p for p in pessoal.build().rows},
        "geotecnico": {g["cod_mun"]: g for g in geo_todos},
        "cobertura": cobertura,
        "regimes": regimes,
        "territorios": territ,
        "estrategias": estrategias,
        "construida": construida,
        "limiar_impermeavel": limiar_imperm,
        "plano": {m["cod_mun"]: m for m in plano.build(cenario, oni)["municipios"]},
    }


def _territorios_do_municipio(cod: int, todos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Territorios tradicionais cujo centroide cai no municipio."""
    return [
            {
                "tipo": t["tipo"],
                "nome": t["nome"],
                "grupo_etnico": t["grupo_etnico"],
                "situacao_juridica": t["situacao_juridica"],
                "area_legal_ha": t["area_legal_ha"],
                "memoria_hidrica_frac": t["agua"]["memoria_hidrica_frac"],
                "km_ate_urgencia": t["km_ate_urgencia"],
            }
            for t in todos
            if t["cod_mun"] == cod
    ]


def build(cod_mun: int, cenario: str = "atual", oni: float | None = None) -> Dossie:
    """Monta o dossie de um municipio a partir de todas as camadas."""
    c = _camadas(cenario, oni)
    tabela = c["tabela"]
    linha = c["por_cod"].get(cod_mun)
    if linha is None:
        raise KeyError(f"municipio {cod_mun} nao esta no RS")

    posicao = c["ranking"].get(cod_mun)
    resp = c["resposta"].get(cod_mun)
    pes = c["pessoal"].get(cod_mun)
    geo = c["geotecnico"].get(cod_mun)
    cobertura = c["cobertura"].get(cod_mun)
    regime = c["regimes"].get(cod_mun)
    plano_mun = c["plano"].get(cod_mun)
    frac_construida = c["construida"].get(cod_mun)
    territ = _territorios_do_municipio(cod_mun, c["territorios"])
    estrategias = c["estrategias"].get(cod_mun, [])

    # ---- lacunas, reunidas de todas as camadas -----------------------------
    # Nao e rodape: e o bloco 7, e vem do payload de cada camada em vez de
    # uma lista escrita a mao aqui — assim uma lacuna nova aparece sozinha.
    lacunas: list[dict[str, str]] = []
    for item in resposta.LACUNAS:
        lacunas.append({"camada": "resposta", **item})
    if geo:
        lacunas.append({
            "camada": "travessias",
            "id": "conservacao_ponte",
            "titulo": "Estado de conservacao das travessias",
            "motivo": geo["pontes"]["nota"],
        })
    lacunas.append({
        "camada": "indice",
        "id": "manutencao_ativos",
        "titulo": "Manutencao de casas de bomba, diques e comportas",
        "motivo": linha["componentes"]["manutencao_ativos"]["detalhe"]["motivo"],
    })
    if territ:
        lacunas.append({
            "camada": "territorios",
            "id": "populacao_territorio",
            "titulo": "Populacao dos territorios tradicionais",
            "motivo": "O poligono nao traz populacao. Converter area exposta em gente exposta "
                      "exige o setor censitario do Censo 2022, nao ingerido.",
        })

    return Dossie({
        "version": VERSION,
        "cod_mun": cod_mun,
        "municipio": linha["municipio"],
        "cenario": tabela.cenario,

        # 1. onde estou
        "posicao": {
            "indice": linha["score"],
            "nivel": linha["level"],
            "basis": linha["basis"],
            "completude": linha["completude"],
            "posicao_no_ranking": posicao,
            "de": c["n_com_score"],
            "populacao": linha["populacao"],
            "regime_cheia": regime,
        },

        # 2. qual o perigo
        "perigo": {
            "componentes": linha["componentes"],
            "memoria_hidrica": linha.get("aguas"),
            "geotecnico": geo["geotecnico"] if geo else None,
            "acesso": geo["acesso"] if geo else None,
            "barragem": geo["barragem"] if geo else None,
            # Fracao de MUNICIPIO, nao de bacia: proxy ordinal. O limiar e o
            # percentil 90 do proprio RS, nao um numero da literatura de
            # hidrologia urbana — que e de bacia e nao se aplica aqui.
            "impermeabilizacao": {
                "frac_construida": frac_construida,
                "limiar_rs": c["limiar_impermeavel"],
                "acima_do_limiar": (
                    None if frac_construida is None or c["limiar_impermeavel"] is None
                    else frac_construida >= c["limiar_impermeavel"]
                ),
                "basis": "measured" if frac_construida is not None else None,
                "nota": "GHSL 2025. Superficie construida e proxy de impermeabilizacao, "
                        "nao medida dela: nao ve piso drenante nem compactacao de solo agricola.",
            } if frac_construida is not None or c["limiar_impermeavel"] is not None else None,
        },

        # 3. quem esta exposto
        "exposicao": {
            "populacao": linha["populacao"],
            "grupos_vulneraveis": resp["vulneraveis"] if resp else None,
            "territorios_tradicionais": territ,
            "n_territorios": len(territ),
        },

        # 4. com o que conto
        "capacidade": {
            "saude": resp["capacidade"] if resp else None,
            "cobertura_recursos": cobertura,
            "pontes": geo["pontes"] if geo else None,
            "quadro_pessoal": pes["quadro"] if pes else None,
            "voluntariado": pes["voluntariado"] if pes else None,
        },

        # 5. o que falhou em 2024
        "falhas_2024": {
            "deficit_prevencao": linha["componentes"]["deficit_prevencao"],
            "autonomia_logistica": resp["autonomia_logistica"] if resp else None,
            "saude_afetada": resp["saude"] if resp else None,
            "resposta_prestada": resp["resposta"] if resp else None,
            "faltou_pessoal": pes["faltou_pessoal_em_2024"] if pes else None,
        },

        # 6. o que fazer
        "acao": {
            "n_acoes": plano_mun["n_acoes"] if plano_mun else 0,
            "n_imediatas": plano_mun["n_imediatas"] if plano_mun else 0,
            "acoes": plano_mun["acoes"] if plano_mun else [],
            "estrategias_contencao": estrategias,
        },

        # 7. o que nao sabemos
        "lacunas": lacunas,
    })
