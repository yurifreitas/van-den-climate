"""Territorios quilombolas e indigenas x memoria hidrica x acesso.

Esta camada e a que tem o maior potencial de causar dano se lida errado, por
tres razoes que os testes abaixo travam uma a uma:

  1. **Ausencia nao e ausencia.** Um municipio sem territorio listado pode
     nao ter comunidade — ou pode ter comunidade sem processo fundiario
     aberto. O vies e sistematico e na mesma direcao: quem tem menos acesso a
     Estado tem menos chance de estar mapeado. O resumo e obrigado a dizer
     isso (`test_limites_declaram_o_vies_de_mapeamento`).

  2. **Area nao e gente.** O poligono nao traz populacao. Tratar "% de area
     com memoria hidrica" como "% de pessoas expostas" e o erro obvio, e o
     modulo nao pode oferecer nenhum campo que o convide
     (`test_nunca_afirma_populacao`).

  3. **Terra em estudo nao e terra homologada.** Mesmo poligono, realidades
     opostas em conflito fundiario (`test_situacao_juridica_sempre_presente`).

O quarto teste — `test_km_ate_urgencia_e_linha_reta` — existe porque a
distancia calculada aqui subestima sempre, e num territorio isolado a
diferenca entre 80 km em linha reta e a estrada real e a diferenca entre
chegar e nao chegar.
"""
from __future__ import annotations

import pytest

from src.risk import territorios


@pytest.fixture(scope="module")
def t():
    if not territorios.TERRITORIOS_PARQUET.exists():
        pytest.skip("territorios ausentes — rode `python -m src.ingest.territorios`")
    return territorios.build()


def test_todo_territorio_tem_tipo_e_situacao(t):
    for r in t.rows:
        assert r["tipo"] in {"territorio quilombola", "terra indigena"}
        assert "situacao_juridica" in r


def test_situacao_juridica_sempre_presente(t):
    """Nunca preencher situacao ausente com um rotulo otimista.

    Se a fonte nao declara, o campo fica None e a interface mostra a lacuna.
    Inventar "regularizada" aqui seria afirmar direito que nao foi concedido.
    """
    for r in t.rows:
        s = r["situacao_juridica"]
        assert s is None or isinstance(s, str)
        assert s != ""


def test_nunca_afirma_populacao(t):
    """Nenhum campo de gente. Area exposta != pessoas expostas."""
    proibidos = {"populacao", "pop", "habitantes", "n_pessoas", "familias"}
    for r in t.rows:
        assert not (set(r) & proibidos), set(r) & proibidos


def test_agua_carrega_selo_e_ausencia_e_none(t):
    """Territorio fora da grade da memoria hidrica sai None, nunca 0.0.

    Zero le como "checamos e nao ha agua". None le como "nao cobrimos".
    """
    for r in t.rows:
        a = r["agua"]
        if a["n_celulas_grade"] == 0:
            assert a["basis"] is None
            assert a["memoria_hidrica_frac"] is None
        else:
            assert a["basis"] == "measured"
            assert 0.0 <= a["memoria_hidrica_frac"] <= 1.0


def test_atencao_usa_o_mesmo_limiar_do_plano(t):
    """Dois limiares com o mesmo nome criariam duas listas incomparaveis."""
    for r in t.rows:
        m = r["agua"]["memoria_hidrica_frac"]
        assert r["atencao_memoria"] is (m is not None and m >= territorios.LIMIAR_MEMORIA)


def test_km_ate_urgencia_e_linha_reta(t):
    """Subestima sempre. O resumo e obrigado a dizer isso em `limites`."""
    assert any("linha reta" in l for l in t.resumo["limites"])
    for r in t.rows:
        km = r["km_ate_urgencia"]
        assert km is None or km >= 0


def test_limites_declaram_o_vies_de_mapeamento(t):
    """O limite mais importante da camada: ausencia nao prova ausencia."""
    texto = " ".join(t.resumo["limites"]).lower()
    assert "nao mapeado" in texto or "não mapeado" in texto
    assert "populacao" in texto or "população" in texto
    assert "1984" in texto  # a memoria hidrica nao conhece a cheia de 2024


def test_resumo_conta_o_que_a_lista_contem(t):
    assert t.resumo["n_territorios"] == len(t.rows)
    assert t.resumo["n_com_memoria_hidrica"] == sum(1 for r in t.rows if r["atencao_memoria"])
    assert sum(t.resumo["por_tipo"].values()) == len(t.rows)


def test_ordenado_por_memoria_hidrica(t):
    """A lista abre pelo territorio onde a agua mais voltou — nao alfabetica."""
    ms = [r["agua"]["memoria_hidrica_frac"] or 0 for r in t.rows]
    assert ms == sorted(ms, reverse=True)
