"""Mapa de recursos e vazios de cobertura.

Dois testes carregam este arquivo.

`test_farmacia_nao_entra_como_unidade_movel` — o tipo 43 do CNES tem rotulo
"Unidade Movel de Nivel Pre-Hospitalar" e devolve 3.733 registros no RS,
encabecados por PANVEL FARMACIAS. Incluir 43 teria posto quase quatro mil
farmacias no mapa como ambulancia, e o erro passaria despercebido porque o
total so pareceria "boa cobertura".

`test_nada_se_chama_viatura` — mesma disciplina de "estabelecimento, nunca
leito" (ADR-036): isto e BASE, e nao ha dado publico de frota.
"""
from __future__ import annotations

import pytest

from src.ingest import cnes_rs
from src.risk import recursos


@pytest.fixture(scope="module")
def r():
    if not recursos.CNES_PARQUET.exists():
        pytest.skip("CNES nao ingerido — rode `python -m src.ingest.cnes_rs`")
    return recursos.build()


# ---------------------------------------------------------------------------
# As duas regressoes
# ---------------------------------------------------------------------------
def test_farmacia_nao_entra_como_unidade_movel():
    """O tipo 43 do CNES e farmacia. Nao pode voltar ao catalogo."""
    assert 43 not in cnes_rs.TIPOS


def test_nada_se_chama_viatura(r):
    texto = str(r.resumo).lower()
    assert "viatura" in texto  # a ressalva PRECISA estar escrita
    assert any("nunca viatura" in x.lower() for x in r.resumo["ressalvas"])
    for p in r.pontos:
        assert "viatura" not in str(p.get("papel", "")).lower()


# ---------------------------------------------------------------------------
# Classificacao heuristica das moveis
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("nome", "esperado"),
    [
        ("ASSOCIACAO CORPO DE BOMBEIROS VOLUNTARIOS DE SALVADOR DO SUL", "bombeiro"),
        ("AMBULANCIA JDN5A92", "ambulancia"),
        ("SAMU 192 REGIONAL", "resgate"),
        ("FARMACIA MOVEL", "farmacia_movel"),
        ("UNIDADE ODONTOLOGICA MOVEL PMPF", "odontologica"),
        ("UNIDADE MOVEL DE ATENCAO PRIMARIA A SAUDE 01", "saude_movel"),
        ("XPTO 42", "nao_classificada"),
        (None, "nao_classificada"),
    ],
)
def test_subtipo_movel(nome, esperado):
    assert cnes_rs._subtipo_movel(nome) == esperado


def test_bombeiro_vence_ambulancia_na_ordem():
    """Bombeiro voluntario que opera ambulancia e bombeiro, nao ambulancia —
    a ordem do catalogo decide, e precisa ser estavel."""
    assert cnes_rs._subtipo_movel("CORPO DE BOMBEIROS COM AMBULANCIA") == "bombeiro"


# ---------------------------------------------------------------------------
# Completude da fonte
# ---------------------------------------------------------------------------
def test_osm_e_marcado_como_colaborativo(r):
    """Vazio de OSM nao pode ser lido como vazio do territorio."""
    for papel in ("bombeiro", "policia"):
        assert r.resumo["por_papel"][papel]["completude"] == "colaborativa"


def test_cnes_e_marcado_como_cadastro(r):
    assert r.resumo["por_papel"]["fixo_hospitalar"]["completude"] == "cadastro"
    # as moveis sao cadastro PARCIAL: a frota do SAMU nao esta la
    assert r.resumo["por_papel"]["movel"]["completude"] == "cadastro_parcial"


def test_ressalva_explica_a_frota_do_samu(r):
    assert any("SAMU" in x for x in r.resumo["ressalvas"])


# ---------------------------------------------------------------------------
# Geometria e cobertura
# ---------------------------------------------------------------------------
def test_todo_ponto_esta_dentro_da_caixa_do_rs(r):
    for p in r.pontos:
        assert -34 <= p["lat"] <= -26.5, p
        assert -58 <= p["lon"] <= -49, p


def test_cobertura_cobre_os_497(r):
    assert len(r.por_municipio) == 497


def test_distancia_e_declarada_como_linha_reta(r):
    assert any("linha reta" in x.lower() for x in r.resumo["ressalvas"])


def test_vazios_so_saem_de_municipio_com_indice():
    from src.risk.municipal import MUNIC_PARQUET, build_table

    if not MUNIC_PARQUET.exists():
        pytest.skip("base municipal nao ingerida")
    v = recursos.vazios_priorizados(build_table(1.39).rows, limite=50)
    for m in v:
        assert m["score"] is not None
        assert m["faltas"], m["municipio"]
        assert m["pior_km"] >= recursos.LIMIAR_VAZIO_KM
