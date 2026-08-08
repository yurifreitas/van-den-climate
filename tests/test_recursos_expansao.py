"""Recursos ampliados: abrigo, acesso, infraestrutura, suprimento e exposicao.

A camada saiu de sete papeis (socorro) para dezessete, e o crescimento traz
tres riscos novos. Os testes aqui existem para cada um deles:

  1. **Somar o que nao se soma.** Com dezessete papeis a tentacao obvia e um
     "total de recursos". Hospital e supermercado respondem perguntas
     diferentes, e a soma nao significa nada — dai as familias, e dai o teste
     que exige que todo papel pertenca a uma.

  2. **Abrigo virar cadastro.** Escola e ginasio no OSM sao predio grande e
     coberto. Nao declaram capacidade, banheiro, cozinha nem gerador, e a
     lista real de abrigos e decisao da Defesa Civil municipal, que nao
     publica. Qualquer campo de "vagas" aqui seria inventado, e
     `test_abrigo_nunca_emite_capacidade` proibe.

  3. **Exposicao hidrica virar laudo.** O cruzamento com a memoria hidrica do
     JRC diz "nesta quadra de ~500 m ja houve agua entre 1984 e 2021". Nao diz
     que o predio alaga: nao ha cota, profundidade nem defesa, e predio atras
     de dique aparece exposto do mesmo jeito. A nota que diz isso e obrigatoria.
"""
from __future__ import annotations

import pytest

from src.risk import recursos


@pytest.fixture(scope="module")
def r():
    return recursos.build()


# ---------------------------------------------------------------------------
# Familias
# ---------------------------------------------------------------------------
def test_todo_papel_pertence_a_uma_familia():
    for papel, info in recursos.PAPEIS.items():
        assert info["familia"] in recursos.FAMILIAS, papel


def test_familias_chegam_no_payload(r):
    assert r.resumo["familias"] == recursos.FAMILIAS
    for info in r.resumo["por_papel"].values():
        assert info["familia"] in recursos.FAMILIAS


def test_ressalva_diz_que_papeis_nao_se_somam(r):
    junto = " ".join(r.resumo["ressalvas"]).lower()
    assert "nao se somam" in junto or "não se somam" in junto


# ---------------------------------------------------------------------------
# Abrigo
# ---------------------------------------------------------------------------
def test_abrigo_nunca_emite_capacidade(r):
    """Nenhum campo pode sugerir vaga, leito ou lotacao de abrigo."""
    proibidos = ("capacidade", "vagas", "lotacao", "leitos_abrigo", "pessoas")
    for papel, info in r.resumo["por_papel"].items():
        if recursos.PAPEIS[papel]["familia"] != "abrigo":
            continue
        for campo in info:
            assert not any(p in campo.lower() for p in proibidos), (papel, campo)


def test_abrigo_declarado_como_potencial(r):
    junto = " ".join(r.resumo["ressalvas"]).lower()
    assert "abrigo e potencial" in junto or "abrigo é potencial" in junto
    assert "defesa civil" in junto
    for papel in ("abrigo_escola", "abrigo_comunitario", "abrigo_religioso"):
        assert r.resumo["por_papel"][papel]["completude"] == "colaborativa"


def test_municipios_sem_abrigo_e_fila_de_verificacao(r):
    """Existe e e pequeno — se explodir, o mapa ralou, nao a cidade sumiu."""
    n = r.resumo["municipios_sem_abrigo_mapeado"]
    assert 0 <= n < 100


# ---------------------------------------------------------------------------
# Exposicao hidrica
# ---------------------------------------------------------------------------
def test_exposicao_carrega_a_propria_nota(r):
    e = r.resumo["exposicao_hidrica"]
    nota = e["nota"].lower()
    assert "quadra" in nota or "celula" in nota
    assert "dique" in nota
    assert e["limiar_frac_celula"] == recursos.LIMIAR_EXPOSICAO_HIDRICA


def test_exposicao_avalia_todos_os_pontos(r):
    e = r.resumo["exposicao_hidrica"]
    assert e["n_avaliados"] >= len(r.pontos)
    assert 0 < e["n_expostos"] < e["n_avaliados"]


def test_infraestrutura_expoe_mais_que_suprimento(r):
    """O achado da camada, e ele e explicavel por projeto, nao por acaso.

    Captacao de agua PRECISA ficar junto do rio; subestacao procura terreno
    plano e barato, que na planicie e a varzea. Supermercado segue a rua
    comercial. Se esta ordem se inverter, alguma coisa mudou na classificacao
    ou no cruzamento — e vale investigar antes de publicar.
    """
    t = r.resumo["exposicao_hidrica"]["taxa_por_familia"]
    assert t["infraestrutura"]["taxa"] > t["suprimento"]["taxa"] * 2


def test_criticos_expostos_so_traz_papel_critico(r):
    criticos = r.resumo["exposicao_hidrica"]["criticos_expostos"]
    assert criticos
    for c in criticos:
        assert c["papel"] in recursos.PAPEIS_CRITICOS_EXPOSICAO
        assert c["memoria_hidrica_frac"] >= recursos.LIMIAR_EXPOSICAO_HIDRICA
    ordenado = [c["memoria_hidrica_frac"] for c in criticos]
    assert ordenado == sorted(ordenado, reverse=True)


def test_cobertura_municipal_traz_exposicao(r):
    algum = next(iter(r.por_municipio.values()))
    for papel, v in algum.items():
        assert "familia" in v
        assert "n_expostos_a_agua" in v
        # Zero exposto so pode aparecer onde HA recurso: sem recurso nenhum, o
        # campo e None. A distincao e a diferenca entre "nenhum alaga" e
        # "nenhum existe".
        if v["n_no_municipio"] == 0:
            assert v["n_expostos_a_agua"] is None, papel


# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------
def test_ponte_nao_viaja_como_recurso(r):
    """Ponte e da camada geotecnica; aqui nunca foi desenhada e pesava 2,1 mil."""
    assert all(p["papel"] in recursos.PAPEIS for p in r.pontos)


def test_coordenada_arredondada(r):
    """5 casas (~1 m) num mapa estadual: o resto e ruido caro de transportar."""
    for p in r.pontos[:200]:
        assert round(p["lat"], 5) == p["lat"]
        assert round(p["lon"], 5) == p["lon"]
