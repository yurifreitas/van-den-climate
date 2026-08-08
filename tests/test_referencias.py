"""Contrato do catalogo de referencias.

A tela de Referencias e a unica pagina do produto que declara de onde vem o
metodo. Ela apodrece de tres formas, e todas ja aconteceram uma vez aqui:

  1. **Nome sem obra.** Ate 2026-08-08, 83 das 86 pessoas tinham `resolve` e
     nao tinham `work`: o leitor ficava sabendo que devia ler Runge e nao
     sabia O QUE ler. Uma referencia que nao se consegue abrir nao e
     referencia, e reputacao. `test_toda_pessoa_tem_obra` fecha isso.

  2. **Citacao inventada para preencher campo.** O remedio da forma (1) tem um
     efeito colateral obvio: forjar um titulo redondo onde a contribuicao e
     dispersa. Isso seria pior que o vazio — passaria a afirmar fonte
     verificavel inexistente, o mesmo modo de falha que a ADR-002 persegue nos
     numeros. A convencao e declarar a dispersao com "Corpo de trabalho", e
     `test_obra_dispersa_se_declara` verifica que a valvula existe e e usada.

  3. **Lacuna generica.** `resolve` que serve para qualquer projeto ("otima
     referencia em clima") nao seleciona nada. O catalogo so tem valor porque
     cada entrada aponta uma lacuna nossa.

Os precedentes construtivos tem contrato proprio, em
`tests/test_referencias_construtivas.py`.
"""
from __future__ import annotations

import pytest

from api.routers.references import _build_catalog


@pytest.fixture(scope="module")
def cat():
    return _build_catalog()


@pytest.fixture(scope="module")
def pessoas(cat):
    return [(s.id, p) for s in cat.schools for p in s.people]


def test_ha_catalogo(pessoas):
    assert len(pessoas) >= 80
    ids = [p.id for _, p in pessoas]
    assert len(set(ids)) == len(ids), "id de pessoa repetido entre escolas"


def test_toda_pessoa_tem_obra(pessoas):
    """Sem obra, a entrada informa reputacao e nao leitura."""
    sem = [f"{esc}/{p.id}" for esc, p in pessoas if not (p.work or "").strip()]
    assert not sem, f"pessoa sem `work`: {sem}"


def test_toda_pessoa_tem_lacuna_nomeada(pessoas):
    """`resolve` curto demais nao consegue nomear lacuna nenhuma."""
    curtos = [f"{esc}/{p.id}" for esc, p in pessoas if len(p.resolve.strip()) < 40]
    assert not curtos, f"`resolve` sem lacuna nomeada: {curtos}"


def test_obra_dispersa_se_declara(pessoas):
    """A valvula de escape existe — e e explicita, nunca uma citacao forjada.

    Entradas institucionais (servico operacional, base colaborativa, corpo
    academico disperso) nao tem peca unica. Elas dizem isso.
    """
    dispersas = [p for _, p in pessoas if p.work.strip().startswith("Corpo de trabalho")]
    assert dispersas, "ninguem usa a valvula — sinal de que viraram citacao redonda"
    assert len(dispersas) < len(pessoas) * 0.2, "dispersao demais: o catalogo perdeu o pe"


def test_reading_order_aponta_para_pessoa_existente(cat, pessoas):
    """Ordem de leitura orfa manda o leitor para um id que nao existe mais."""
    ids = {p.id for _, p in pessoas}
    faltando = [i for i in cat.reading_order if i not in ids]
    assert not faltando, f"reading_order aponta para inexistente: {faltando}"


def test_precedente_referencia_pessoa_conhecida(cat, pessoas):
    """`by: null` e legitimo (metodo sem autor unico); `by: fulano` inexistente nao."""
    ids = {p.id for _, p in pessoas}
    orfas = [pr.ours for pr in cat.precedents if pr.by and pr.by not in ids]
    assert not orfas, f"precedente aponta para pessoa inexistente: {orfas}"


def test_adversarial_referencia_pessoa_conhecida(cat, pessoas):
    ids = {p.id for _, p in pessoas}
    orfas = [a.claim for a in cat.adversarial if a.by and a.by not in ids]
    assert not orfas, f"leitura adversarial aponta para pessoa inexistente: {orfas}"


def test_adversarial_declara_consequencia(cat):
    """Contra-argumento sem consequencia no projeto e ornamento intelectual."""
    for a in cat.adversarial:
        assert len(a.consequence.strip()) > 60, a.claim
