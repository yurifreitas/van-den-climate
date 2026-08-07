"""Memoria hidrica — JRC Global Surface Water recortado pela malha municipal.

O teste que da nome ao arquivo e `test_oceano_nao_entra_na_conta`. Ele existe
porque a primeira versao contou o Atlantico: o recorte era um retangulo em
volta do RS, e "agua permanente" deu 106.000 km² num estado de 281.000 —
numero que so podia sair de somar o mar. Erro de mascara e silencioso: nao
levanta excecao, nao aparece no tipo, e produz um mapa que continua bonito.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.risk import aguas


@pytest.fixture(scope="module")
def tabela():
    df = aguas.load()
    if df is None:
        pytest.skip("camada de agua nao calculada — rode `python -m src.risk.aguas`")
    return df


@pytest.fixture(scope="module")
def meta():
    m = aguas.load_meta()
    if m is None:
        pytest.skip("camada de agua nao calculada")
    return m


# ---------------------------------------------------------------------------
# A regressao do oceano
# ---------------------------------------------------------------------------
def test_oceano_nao_entra_na_conta(meta):
    """Area total na grade tem de ficar dentro da area do RS (281.730 km²).

    Folga para baixo porque a malha do IBGE em 'qualidade minima' e
    generalizada e a grade tem 500 m; folga para cima, nenhuma — passar da
    area do estado so pode significar pixel de fora.
    """
    area = meta["area_estado_km2"]
    assert 250_000 < area < 281_730, f"area da grade fora do plausivel: {area}"


def test_agua_permanente_e_fracao_pequena_do_estado(meta):
    """RS nao e 40% agua. Sanidade grossa contra mascara furada."""
    perm = meta["total_km2"]["permanente"]
    assert 0 < perm < 0.10 * meta["area_estado_km2"]


def test_soma_dos_municipios_bate_com_o_total_do_estado(tabela, meta):
    for cat in aguas.CATEGORIAS:
        soma = float(tabela[f"agua_{cat}_km2"].sum())
        assert soma == pytest.approx(meta["total_km2"][cat], rel=0.02)


# ---------------------------------------------------------------------------
# Contrato da tabela
# ---------------------------------------------------------------------------
def test_cobre_os_497_municipios(tabela):
    assert len(tabela) == 497
    assert tabela["cod_mun"].nunique() == 497


def test_nenhuma_area_negativa(tabela):
    for cat in aguas.CATEGORIAS:
        assert (tabela[f"agua_{cat}_km2"] >= 0).all()


def test_fracao_entre_zero_e_um(tabela):
    for cat in aguas.CATEGORIAS:
        col = tabela[f"frac_{cat}"].dropna()
        assert ((col >= 0) & (col <= 1)).all()


def test_agua_nao_excede_a_area_do_municipio(tabela):
    """Categorias sao exclusivas no raster: a soma nao pode passar do total."""
    soma = sum(tabela[f"agua_{c}_km2"] for c in aguas.CATEGORIAS)
    assert (soma <= tabela["area_grade_km2"] * 1.001).all()


# ---------------------------------------------------------------------------
# Semantica das categorias
# ---------------------------------------------------------------------------
def test_categorias_cobrem_as_classes_do_jrc_sem_sobreposicao():
    """Uma classe do JRC nao pode cair em duas categorias — dobraria area."""
    from src.ingest.jrc_gsw import CATEGORIAS as CATS

    vistas: list[int] = []
    for classes in CATS.values():
        vistas.extend(classes)
    assert len(vistas) == len(set(vistas)), "classe do JRC em mais de uma categoria"
    # classe 0 e 'sem mudanca / nao e agua' e nao pode entrar em nenhuma
    assert 0 not in vistas


def test_agua_perdida_e_classe_de_perda():
    """`perdida` tem de ser exatamente lost-permanent e lost-seasonal."""
    from src.ingest.jrc_gsw import CATEGORIAS as CATS

    assert set(CATS["perdida"]) == {3, 6}


def test_pintura_poe_agua_de_hoje_sobre_agua_de_antes():
    """Ordem de pintura importa: a margem de todo rio tem historico de agua.

    Se `perdida` pintasse por cima de `permanente`, o mapa acusaria de passivo
    hidrico a margem de cada rio do estado — o oposto da leitura correta.
    """
    ordem = list(aguas.ORDEM_PINTURA)
    assert ordem.index("permanente") > ordem.index("perdida")
    assert ordem.index("sazonal") > ordem.index("efemera")


# ---------------------------------------------------------------------------
# Integracao com o indice: presente na linha, ausente do calculo
# ---------------------------------------------------------------------------
def test_memoria_hidrica_e_perdida_mais_efemera(tabela):
    from src.risk.municipal import _bloco_aguas

    linha = tabela.iloc[0]
    bloco = _bloco_aguas(linha)
    assert bloco is not None
    esperado = (bloco["perdida"]["km2"] or 0) + (bloco["efemera"]["km2"] or 0)
    assert bloco["memoria_hidrica_km2"] == pytest.approx(esperado, abs=0.02)


def test_bloco_aguas_ausente_vira_none_e_nao_zeros():
    """Camada nao calculada tem de sumir da linha, nao virar uma linha de zeros."""
    import pandas as pd

    from src.risk.municipal import _bloco_aguas

    assert _bloco_aguas(pd.Series({"cod_mun": 4300034})) is None
    assert _bloco_aguas(pd.Series({"cod_mun": 4300034, "agua_perdida_km2": np.nan})) is None


def test_memoria_hidrica_fica_fora_do_indice():
    """Regra explicita: a variavel e confundida por arroz irrigado.

    Se alguem a incluir no indice, este teste falha e obriga a passar por uma
    ADR nova em vez de mudar 497 numeros publicados em silencio.
    """
    from src.risk.municipal import PESOS, model_card

    assert set(PESOS) == {"impacto", "deficit", "exposicao"}
    card = model_card()
    assert card["memoria_hidrica"]["no_indice"] is False
    assert "arroz" in card["memoria_hidrica"]["motivo_fora_do_indice"].lower()


def test_limites_declaram_a_janela_e_a_lagoa(meta):
    """1984-2021, nao 150 anos; e a malha do IBGE exclui as grandes lagoas."""
    assert meta["janela"] == "1984-2021"
    assert "2024" in meta["nao_cobre"]
