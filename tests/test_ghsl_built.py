"""GHSL Built-up Surface: fracao construida por municipio.

Dois erros silenciosos rondam esta camada, e os dois produzem numeros que
parecem certos:

  1. **Somar celula como se toda celula tivesse a mesma area.** A grade e em
     graus. Entre o norte e o sul do RS a area de uma celula de 30" varia
     ~9%; contra o Equador, ~17%. Somar direto inflaria o norte e deflacionaria
     o sul — um gradiente falso exatamente na direcao em que o estado varia de
     verdade. `test_area_de_celula_diminui_para_o_sul` trava isso.

  2. **Confundir fracao municipal com cobertura impermeavel de bacia.** Sao
     denominadores diferentes por uma ordem de grandeza, e o limite de 10-25%
     da literatura de hidrologia urbana e de bacia. `test_limites_avisam_que_e
     _proxy_ordinal` exige que o payload diga isso.

O teste de sanidade que vale mais que todos: os oito municipios mais
construidos tem que ser a regiao metropolitana de Porto Alegre. Se essa lista
mudar de forma, o alinhamento do raster quebrou.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.ingest import ghsl_built


@pytest.fixture(scope="module")
def df():
    import pandas as pd

    if not ghsl_built.SAIDA.exists():
        pytest.skip("ghsl_built_rs.parquet ausente — rode `python -m src.ingest.ghsl_built`")
    return pd.read_parquet(ghsl_built.SAIDA)


def test_area_de_celula_diminui_para_o_sul():
    """Nao e detalhe: e a diferenca entre medir e inventar um gradiente."""
    res = 30 / 3600
    norte = ghsl_built._area_celula_m2(np.array([-27.0]), res)[0]
    sul = ghsl_built._area_celula_m2(np.array([-33.7]), res)[0]
    assert sul < norte
    assert 0.85 < sul / norte < 0.95
    # ~1 km de lado na latitude do RS
    assert 0.6e6 < norte < 1.0e6


def test_um_municipio_por_codigo(df):
    assert len(df) == 497
    assert df.cod_mun.is_unique


def test_fracao_no_intervalo_e_ausencia_nunca_zero(df):
    f = df.frac_construida.dropna()
    assert ((f >= 0) & (f <= 1)).all()
    # Municipio sem celulas suficientes sai None, nunca 0.0 — zero leria como
    # "medimos e nao ha nada construido".
    sem = df[df.frac_construida.isna()]
    assert (sem.basis.isna()).all()
    assert (df[df.frac_construida.notna()].basis == "measured").all()


def test_construido_nunca_excede_a_grade(df):
    assert (df.km2_construidos <= df.km2_grade + 1e-6).all()


def test_metropolitana_lidera(df):
    """Sanidade de alinhamento do raster, nao descoberta.

    Se o recorte da janela ou o transform escorregar, esta lista deixa de ser
    a regiao metropolitana e vira geografia aleatoria.
    """
    top = set(df.nlargest(8, "frac_construida").municipio)
    metropolitana = {
        "Esteio", "Canoas", "Cachoeirinha", "Sapucaia do Sul",
        "São Leopoldo", "Alvorada", "Porto Alegre", "Novo Hamburgo",
        "Gravataí", "Viamão", "Sapiranga", "Campo Bom",
    }
    assert len(top & metropolitana) >= 6, top


def test_area_total_da_grade_bate_com_o_rs(df):
    """~281 mil km2 no IBGE; a malha exclui Patos e Mirim, entao fica abaixo."""
    total = df.km2_grade.sum()
    assert 240_000 < total < 285_000


def test_limites_avisam_que_e_proxy_ordinal():
    """O limite mais caro da camada viaja junto do numero, no proprio meta."""
    import json

    caminho = ghsl_built.DATA_INTERIM / "ghsl_built_rs.meta.json"
    if not caminho.exists():
        pytest.skip("meta ausente — rode `python -m src.ingest.ghsl_built`")
    texto = " ".join(json.loads(caminho.read_text(encoding="utf-8"))["limites"]).lower()
    assert "proxy" in texto
    assert "ordinal" in texto
    # A pegadinha que o numero nao mostra: solo agricola compactado escoa como
    # cidade e aparece aqui com fracao baixa.
    assert "compacta" in texto
    assert "vazao" in texto or "escoamento" in texto
