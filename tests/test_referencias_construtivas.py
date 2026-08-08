"""Precedentes construtivos atipicos — o catalogo que amplia o repertorio.

Duas formas de esta secao apodrecer sem ninguem notar:

  1. **Orfandade.** `aplicavel_a` aponta para ids de estrategia em
     `src/risk/contencao.py`. Renomear uma estrategia la deixa a referencia
     apontando para o nada, e a interface segue mostrando a tag como se
     significasse algo. `test_todo_aplicavel_a_existe` amarra os dois.

  2. **Virar propaganda.** Uma obra estrangeira listada sem o limite dela e um
     folheto. Foi assim que o dique continuo virou resposta padrao no RS: o
     precedente holandes chegou, o modo de falha nao. `test_limite_obrigatorio`
     nao deixa entrar entrada sem onde-nao-resolve.

O terceiro teste existe para manter a secao honesta na outra direcao: se toda
entrada fosse baseada na natureza, isto seria preferencia estetica com cara de
catalogo. `test_ha_precedente_convencional_caro` exige que o extremo caro e
enterrado esteja representado.
"""
from __future__ import annotations

import pytest

from api.routers.references import _build_catalog
from src.risk import contencao


@pytest.fixture(scope="module")
def cat():
    return _build_catalog().construtivos


def test_catalogo_nao_esta_vazio(cat):
    assert len(cat) >= 8
    assert len({c.id for c in cat}) == len(cat)


def test_todo_aplicavel_a_existe(cat):
    """Tag orfa e pior que tag ausente: parece ligacao e nao e."""
    ids = {e.id for e in contencao.ESTRATEGIAS}
    for c in cat:
        assert c.aplicavel_a, c.id
        faltando = set(c.aplicavel_a) - ids
        assert not faltando, f"{c.id} aponta para estrategia inexistente: {faltando}"


def test_toda_estrategia_tem_ao_menos_um_precedente(cat):
    """Estrategia sem precedente atipico e a que fica so com o repertorio padrao."""
    cobertas = {a for c in cat for a in c.aplicavel_a}
    orfas = {e.id for e in contencao.ESTRATEGIAS} - cobertas
    assert not orfas, f"sem precedente atipico: {orfas}"


def test_limite_obrigatorio(cat):
    """Precedente sem limite e propaganda — e obra importada sem o modo de
    falha dela e como o dique continuo chegou aqui."""
    for c in cat:
        assert len(c.limite) > 80, c.id
        assert c.fonte.strip(), c.id


def test_cada_entrada_diz_onde_e_quando(cat):
    """Sem lugar e data, o precedente vira anedota e nao da para ir checar."""
    for c in cat:
        assert c.onde.strip(), c.id
        assert any(ch.isdigit() for ch in c.quando), c.id


def test_ha_precedente_convencional_caro(cat):
    """Contrapeso deliberado.

    Se todas as entradas fossem baseadas na natureza, a secao seria preferencia
    estetica disfarcada de catalogo. O extremo oposto — enterrar volume e
    bombear — precisa estar representado, porque ha caso em que ele e a unica
    resposta.
    """
    texto = " ".join(f"{c.titulo} {c.por_que_atipica}" for c in cat).lower()
    assert "bombe" in texto or "tunel" in texto


def test_ha_precedente_que_nao_e_obra(cat):
    """O gargalo de varzea no Brasil e fundiario, nao de engenharia."""
    assert any("fundiario" in c.mecanismo or "contrato" in c.por_que_atipica.lower() for c in cat)
