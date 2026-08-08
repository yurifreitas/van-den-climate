"""Degradacao do solo — e a disciplina de nao transformar tabela em medida.

O risco desta camada nao e errar o numero: e o numero ser CRIDO. Uma equacao
com quatro fatores de tabela devolve um valor com uma casa decimal, e uma casa
decimal parece medicao. Os testes aqui existem sobretudo para manter as
salvaguardas de leitura no lugar:

  - a classe publicada e posicao no estado, nunca corte absoluto importado;
  - o nome do campo diz que e indice, nao tonelada perdida;
  - os numeros MEDIDOS (area de uso intensivo em declive, solo raso sob
    lavoura) continuam existindo separados, para que a camada sobreviva a
    contestacao do indice;
  - a nota de escala nao some.

O sinal fisico tambem e verificado, mas contra o mapa: se o Alto Uruguai (solo
raso, encosta forte) nao aparecer acima da planicie costeira (arenosa, plana),
os fatores foram trocados de lugar.
"""
from __future__ import annotations

import pytest

from src.risk import degradacao as d


def test_latossolo_resiste_mais_que_argissolo():
    """A inversao da intuicao: argila estruturada resiste, B textural nao."""
    assert d.fator_k("LATOSSOLO", "muito argilosa") < d.fator_k("ARGISSOLO", "arenosa/argilosa")


def test_ls_cresce_com_o_relevo():
    seq = ["plano", "suave ondulado", "ondulado", "forte ondulado", "montanhoso"]
    valores = [d.fator_ls(r) for r in seq]
    assert valores == sorted(valores)
    # O salto do plano ao montanhoso e de ordem de grandeza — e por isso que
    # trocar a classe qualitativa por declividade real e a melhoria de maior
    # retorno da camada.
    assert valores[-1] / valores[0] > 20


def test_ls_aceita_rotulo_com_quebra_de_linha():
    """O WFS entrega 'suave \\nondulado'; a normalizacao vive na ingestao, mas
    se ela falhar aqui o LS cai no padrao sem avisar."""
    assert d.fator_ls("suave ondulado") == d.LS_POR_RELEVO["suave ondulado"]
    assert d.fator_ls("SUAVE ONDULADO") == d.LS_POR_RELEVO["suave ondulado"]


def test_erosividade_cresce_com_a_chuva():
    assert d.erosividade_r(1200) < d.erosividade_r(1800)
    assert d.erosividade_r(0) > 0     # sem divisao por zero nem negativo


@pytest.fixture(scope="module")
def resultado():
    return d.build()


def test_classe_e_posicao_no_estado(resultado):
    """Nenhum corte absoluto: o rotulo tem que citar o RS."""
    for r in resultado.rows:
        assert "RS" in r["classe"], r["classe"]
    # E a posicao tem que ser coerente com o percentil que a gerou.
    topo = resultado.rows[0]
    assert topo["percentil_rs"] >= 0.9


def test_campo_diz_que_e_indice(resultado):
    """`perda_t_ha_ano` seria lido como tonelada perdida. Nao e."""
    r = resultado.rows[0]
    assert "indice_rusle_t_ha_ano" in r
    assert "perda_t_ha_ano" not in r


def test_nota_de_escala_sobrevive(resultado):
    nota = resultado.resumo["nota_escala"].lower()
    assert "posicao" in nota and "quantidade" in nota


def test_numeros_medidos_existem_separados(resultado):
    """Se o indice cair, estes continuam de pe: sao area cruzando duas classes."""
    r = resultado.rows[0]
    for campo in ("km2_uso_intensivo_em_declive", "km2_solo_raso_sob_uso_intensivo",
                  "km2_cobertura_permanente_em_declive"):
        assert campo in r
        assert r[campo] >= 0
    assert resultado.resumo["km2_uso_intensivo_em_declive_rs"] > 0


def test_p_assumido_declarado(resultado):
    """P=1 e a hipotese que mais infla o resultado. Tem que estar visivel."""
    assert resultado.resumo["p_assumido"] == 1.0
    assert any("P=1" in x for x in resultado.limites)


def test_encosta_do_alto_uruguai_acima_da_planicie_costeira(resultado):
    por_nome = {r["municipio"]: r for r in resultado.rows}
    assert (por_nome["Itatiba do Sul"]["indice_rusle_t_ha_ano"]
            > 10 * por_nome["Rio Grande"]["indice_rusle_t_ha_ano"])


def test_vocoroca_e_deslizamento_declarados_fora(resultado):
    junto = " ".join(resultado.limites).lower()
    assert "vocoroca" in junto
    assert "deslizamento" in junto
