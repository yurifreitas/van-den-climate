"""Declividade medida — e a disciplina de nao trocar um adjetivo por outro.

O Copernicus DEM entrou para corrigir um fator com alavanca grande: LS cresce
quarenta vezes do plano ao montanhoso, e essa diferenca estava sendo decidida
pelo adjetivo da carta pedologica, que descreve o poligono inteiro pela feicao
predominante em area.

Tres coisas precisam continuar verdadeiras para a troca ter valido a pena:

  1. **A reancoragem preserva a forma.** O DEM da UM numero por municipio; a
     carta diz qual PARTE dele e mais ingreme. Se o codigo passar a usar so o
     DEM, a variacao interna some e a camada perde a razao de cruzar solo com
     relevo.

  2. **O fator e publicado.** Sem isso a troca de metodo aparece como um numero
     novo sem explicacao — e a mediana perto de 1 esconderia que o fator varia
     de 0,1 a 2,6 entre municipios.

  3. **A declividade separa o que o adjetivo juntava.** Santa Vitoria do Palmar
     (planicie lagunar) e Relvado (encosta do Taquari) tinham a mesma resposta
     ordinal antes; agora nao tem.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.ingest import copernicus_dem as dem
from src.risk import degradacao as dg
from src.risk import hidrologia as h

PARQUET = Path(__file__).resolve().parents[1] / "data" / "interim" / "copernicus_dem_rs.parquet"


def test_ls_cresce_com_a_declividade_medida():
    import numpy as np

    pcts = np.array([1.0, 5.0, 15.0, 30.0, 60.0])
    ls = dem.fator_ls(pcts)
    assert list(ls) == sorted(ls)
    # A alavanca que justifica a fonte: do quase plano ao montanhoso, uma ordem
    # de grandeza no fator.
    assert ls[-1] / ls[0] > 15


def test_ls_nao_fica_negativo_em_terreno_plano():
    """A formula de McCool com quebra em 9% pode passar do zero se aplicada
    sem piso — e LS negativo viraria erosao negativa, que nao existe."""
    import numpy as np

    assert (dem.fator_ls(np.array([0.0, 0.1, 1.0])) >= 0).all()


@pytest.fixture(scope="module")
def relevo():
    if not PARQUET.exists():
        pytest.skip("DEM nao ingerido — rode `python -m src.ingest.copernicus_dem`")
    import pandas as pd

    return pd.read_parquet(PARQUET)


def test_declividade_do_estado_e_plausivel(relevo):
    """Faixa larga, para detectar absurdo — nao para calibrar.

    Espacamento metrico errado (fixo em vez de por latitude) ou confusao de
    unidade apareceriam aqui como um estado inteiro plano ou vertical.
    """
    media = float(relevo.declividade_media_pct.mean())
    assert 5.0 < media < 25.0, media
    assert relevo.declividade_media_pct.max() < 80.0
    assert (relevo.altitude_media_m.between(-10, 1400)).all()


def test_fracoes_de_classe_somam_um(relevo):
    cols = [c for c in relevo.columns if c.startswith("frac_")]
    soma = relevo[cols].sum(axis=1)
    assert soma.between(0.99, 1.01).all()


def test_planicie_e_serra_nao_se_confundem(relevo):
    por_nome = relevo.set_index("municipio")
    assert por_nome.loc["Santa Vitória do Palmar", "declividade_media_pct"] < 3
    assert por_nome.loc["Itati", "declividade_media_pct"] > 20


# ---------------------------------------------------------------------------
# Integracao com as camadas
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def degradacao(relevo):
    return dg.build()


def test_reancoragem_publica_o_proprio_fator(degradacao):
    r = degradacao.resumo["reancoragem"]
    assert r["disponivel"]
    assert 0.5 < r["fator_mediano"] < 2.0
    # O achado que justifica a fonte: acerta na media, erra por municipio.
    assert r["n_carta_subestimou"] > 50
    assert r["n_carta_superestimou"] > 20
    assert "media" in r["nota"].lower() or "média" in r["nota"].lower()


def test_reancoragem_preserva_a_ordem_interna(degradacao):
    """Se o DEM substituisse a carta, todo poligono do municipio teria o mesmo
    LS e `onde_mais_perde` viraria uma lista ordenada so por area."""
    for linha in degradacao.rows[:20]:
        indices = [d["indice_t_ha_ano"] for d in linha["onde_mais_perde"]]
        if len(indices) > 2:
            assert len(set(indices)) > 1, linha["municipio"]
            break
    else:
        pytest.fail("nenhum municipio com variacao interna de perda")


def test_hidrologia_usa_declividade_medida(relevo):
    r = h.build()
    assert r.resumo["n_com_declividade_medida"] >= 490
    por_nome = {x["municipio"]: x for x in r.rows}
    # O adjetivo juntava os dois; a medida separa.
    assert por_nome["Santa Vitória do Palmar"]["resposta"] == "lenta"
    assert por_nome["Relvado"]["resposta"] in ("rapida", "muito rapida")


def test_limite_do_dem_declarado():
    r = h.build()
    junto = " ".join(r.limites).lower()
    assert "superficie" in junto and "dossel" in junto
