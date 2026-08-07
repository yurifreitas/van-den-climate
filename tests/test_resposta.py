"""Resposta, vulnerabilidade, capacidade e autonomia logistica.

Dois testes carregam o peso deste arquivo:

`test_capacidade_nunca_se_chama_leito` — o dado e ESTABELECIMENTO. A razao
entre estabelecimento e leito varia de 10 a 400 entre um hospital de interior
e um terciario. Chamar um de outro numa central de risco vira decisao de
encaminhamento errada, e e um erro que passa despercebido porque o numero
continua plausivel.

`test_nao_necessitou_nao_vira_nota_maxima` — municipio que nao precisou de
resgate nao demonstrou capacidade de resgate. Tratar "nao houve/nao
necessitou" como 1.0 premiaria quem foi poupado e enterraria quem foi
testado, invertendo o sinal que a escala existe para medir.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.risk import resposta as r


@pytest.fixture(scope="module")
def tabela():
    if not r.MUNIC_PARQUET.exists():
        pytest.skip("base municipal nao ingerida — rode `python -m src.ingest.ibge_rs`")
    return r.build_table()


def _linha(**over) -> pd.Series:
    base = {"cod_mun": 4300000, "municipio": "Teste", "populacao": 10_000}
    for col in (*r.GRUPOS, *r.SAUDE, *r.RESPOSTA):
        base.setdefault(col, False)
    for col in r.ESCALAS:
        base.setdefault(col, "Não houve/não necessitou")
    base.update(over)
    return pd.Series(base)


# ---------------------------------------------------------------------------
# As duas regressoes que dao nome ao arquivo
# ---------------------------------------------------------------------------
def test_capacidade_nunca_se_chama_leito(tabela):
    for linha in tabela.rows:
        assert linha["capacidade"]["unidade"] == "estabelecimentos"
        assert "leito" not in str(linha["capacidade"]).lower()
    assert tabela.resumo["capacidade"]["unidade"] == "estabelecimentos"


def test_nao_necessitou_nao_vira_nota_maxima():
    """Todas as sete escalas em 'nao necessitou' => indice None, nunca 1.0."""
    aut = r._autonomia(_linha())
    assert aut["indice"] is None
    assert aut["n_aplicaveis"] == 0
    assert all(item["aplicavel"] is False for item in aut["itens"])


def test_escala_aplicavel_entra_no_indice():
    aut = r._autonomia(_linha(log_tempo_primeira_resposta="Logo após o início do evento"))
    assert aut["indice"] == 1.0
    assert aut["n_aplicaveis"] == 1


def test_indice_e_media_so_das_aplicaveis():
    aut = r._autonomia(
        _linha(
            log_tempo_primeira_resposta="Mais de 3 dias após o início",  # 0.15
            log_recursos_durante="Disponíveis conforme as necessidades",  # 1.0
        )
    )
    assert aut["n_aplicaveis"] == 2
    assert aut["indice"] == pytest.approx((0.15 + 1.0) / 2, abs=1e-6)


# ---------------------------------------------------------------------------
# Lacunas declaradas
# ---------------------------------------------------------------------------
def test_lacunas_cobrem_o_que_foi_pedido_e_nao_existe(tabela):
    ids = {l["id"] for l in tabela.lacunas}
    assert {"leitos", "dias_letivos", "recuperacao_financeira",
            "recuperacao_psicologica", "recuperacao_estrutural"} <= ids
    for l in tabela.lacunas:
        assert l["motivo"], f"lacuna {l['id']} sem motivo"


def test_lacuna_de_leitos_nomeia_a_fonte_que_resolveria(tabela):
    leitos = next(l for l in tabela.lacunas if l["id"] == "leitos")
    assert "CNES-LT" in leitos["motivo"]


# ---------------------------------------------------------------------------
# Contrato da tabela
# ---------------------------------------------------------------------------
def test_cobre_os_497(tabela):
    assert len(tabela.rows) == 497
    assert len({x["cod_mun"] for x in tabela.rows}) == 497


def test_municipio_sem_unidade_tem_distancia_e_vice_versa(tabela):
    """Ou o municipio tem unidade, ou sabe a que distancia esta a mais proxima."""
    for linha in tabela.rows:
        cap = linha["capacidade"]
        if cap["total"] == 0:
            assert cap["km_ate_unidade_mais_proxima"] is not None
            assert cap["km_ate_unidade_mais_proxima"] >= 0
        else:
            assert cap["km_ate_unidade_mais_proxima"] is None


def test_todo_bloco_com_conteudo_tem_basis(tabela):
    """Numero sem selo e bug de interface (contrato §0)."""
    for linha in tabela.rows:
        if linha["vulneraveis"]["grupos"]:
            assert linha["vulneraveis"]["basis"] == "measured"
        if linha["saude"]["impactos"]:
            assert linha["saude"]["basis"] == "measured"
        if linha["autonomia_logistica"]["indice"] is not None:
            assert linha["autonomia_logistica"]["basis"] == "measured"


def test_apoio_psicologico_distingue_nao_de_ausente(tabela):
    """False (nao ofereceu) e None (nao informou) sao estados diferentes."""
    valores = {linha["resposta"]["apoio_psicologico"] for linha in tabela.rows}
    assert True in valores and False in valores and None in valores


def test_resumo_declara_por_que_fica_fora_do_indice(tabela):
    assert "predisposi" in tabela.resumo["fora_do_indice"].lower()


def test_capacidade_nao_entra_no_indice_de_prioridade():
    """Trava explicita: se alguem somar isto ao indice, o teste cai."""
    from src.risk.municipal import PESOS

    assert set(PESOS) == {"impacto", "deficit", "exposicao"}
