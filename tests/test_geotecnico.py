"""Perigo geotecnico, acesso e travessias.

O teste central e `test_ponte_nunca_afirma_conservacao`. Ha 2.159 travessias
mapeadas na malha principal do RS e ZERO laudo publico: nao existe dado de
estado de conservacao, vao, carga ou ano de construcao para nenhuma delas.

Um painel que liste pontes ao lado de um indice de risco convida a leitura
"estas pontes estao ruins". Ela seria invencao. A unica afirmacao que o dado
sustenta e "ha N travessias por onde o acesso deste municipio passa" — e por
isso a acao correspondente e VISTORIA (onde procurar), nunca reparo.

Mesma disciplina de ADR-036 (estabelecimento, nunca leito) e ADR-053 (base,
nunca viatura).
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.risk import geotecnico, municipal


@pytest.fixture(scope="module")
def g():
    if not geotecnico.MUNIC_PARQUET.exists():
        pytest.skip("base municipal nao ingerida — rode `python -m src.ingest.ibge_rs`")
    return geotecnico.build()


# ---------------------------------------------------------------------------
# A regressao que da nome ao arquivo
# ---------------------------------------------------------------------------
def test_ponte_nunca_afirma_conservacao(g):
    texto = str(g.resumo).lower()
    assert "conservacao" in texto  # a ressalva PRECISA estar escrita
    assert any("nao ha dado publico de estado de conservacao" in l.lower()
               or "estado de conservacao" in l.lower() for l in g.resumo["limites"])
    for r in g.rows:
        p = r["pontes"]
        assert "conservacao" in p["nota"]
        # nenhum campo pode sugerir estado
        assert set(p) <= {"n_malha_principal", "n_estruturantes", "raio_km", "basis", "nota"}


def test_vistoria_diz_onde_procurar_nao_qual_ponte():
    doc = geotecnico.vistoria_prioritaria.__doc__ or ""
    assert "onde procurar" in doc.lower()
    assert "nao e lista de pontes com problema" in doc.lower()


# ---------------------------------------------------------------------------
# Separacao entre hidrico e geotecnico
# ---------------------------------------------------------------------------
def test_geotecnico_nao_entra_no_indice_hidrico():
    """A exclusao e deliberada (fisica e mitigacao diferentes) e tem de ficar.

    Se alguem mover deslizamento para PERIGOS_HIDRICOS, este teste cai e
    obriga a passar por uma ADR — em vez de mudar 497 numeros em silencio.
    """
    hidricos = set(municipal.PERIGOS_HIDRICOS)
    geotecnicos = set(geotecnico.GEOTECNICO)
    assert not (hidricos & geotecnicos), "perigo geotecnico vazou para o indice hidrico"


def test_queda_de_barreira_conta_nos_dois_por_motivos_diferentes():
    """Unica sobreposicao legitima: barreira e talude (geotecnico) E corta
    estrada (acesso). Nao e duplicacao — sao duas leituras do mesmo fato."""
    assert "oc_queda_barreira" in geotecnico.GEOTECNICO
    assert "oc_queda_barreira" in geotecnico.ACESSO
    assert "oc_queda_barreira" not in municipal.PERIGOS_HIDRICOS


# ---------------------------------------------------------------------------
# Ausencia versus zero
# ---------------------------------------------------------------------------
def test_sem_resposta_vira_none_nao_zero():
    linha = pd.Series({"cod_mun": 1})
    score, ativos = geotecnico._score(linha, geotecnico.GEOTECNICO)
    assert score is None
    assert ativos == []


def test_respondeu_tudo_nao_vira_zero_medido():
    linha = pd.Series({c: False for c in geotecnico.GEOTECNICO})
    score, ativos = geotecnico._score(linha, geotecnico.GEOTECNICO)
    assert score == 0.0  # zero MEDIDO: respondeu e nao houve
    assert ativos == []


def test_score_limitado_a_um(g):
    for r in g.rows:
        for chave in ("geotecnico", "acesso"):
            s = r[chave]["score"]
            if s is not None:
                assert 0.0 <= s <= 1.0, (r["municipio"], chave)


# ---------------------------------------------------------------------------
# Contrato
# ---------------------------------------------------------------------------
def test_cobre_os_497(g):
    assert g.resumo["n_municipios"] == 497
    assert len(g.rows) == 497


def test_barragem_declara_o_efeito_a_jusante(g):
    """Quem tem a obra pode nao ser quem sofre — precisa estar dito."""
    for r in g.rows:
        assert "jusante" in r["barragem"]["nota"]


def test_limites_declaram_que_nao_e_mapa_de_suscetibilidade(g):
    txt = " ".join(g.resumo["limites"]).lower()
    assert "suscetibilidade" in txt
    assert "snisb" in txt or "inventario" in txt


def test_vistoria_respeita_o_minimo_de_pontes():
    if not geotecnico.MUNIC_PARQUET.exists():
        pytest.skip("base municipal nao ingerida")
    v = geotecnico.vistoria_prioritaria(municipal.build_table(1.39).rows, limite=50)
    for x in v:
        assert x["n_pontes"] >= geotecnico.MIN_PONTES_VISTORIA
        assert x["motivos"]
        assert x["score"] is not None
