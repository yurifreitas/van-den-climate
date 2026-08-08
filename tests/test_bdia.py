"""Ingestao BDiA — as invariantes que o parquet precisa manter.

Esta ingestao ja falhou de duas formas que nao levantam excecao, e as duas
estao travadas aqui:

  1. **Geometria nula.** Com `propertyName` no GetFeature e sem `geom` na
     lista, o GeoServer responde 200, com todas as feicoes, e `geometry:
     null` em cada uma. A rasterizacao pula tudo em silencio e o estado sai
     com 497 municipios e ZERO km2 — um parquet integro afirmando que o RS
     nao tem solo. `test_area_bate_com_o_estado` pega.

  2. **Rotulo quebrado por linha.** O WFS entrega "suave \\nondulado",
     herdado da diagramacao da carta impressa. Sem normalizar, o mesmo relevo
     vira duas classes e todo mapeamento a jusante erra a metade que nao
     previu. `test_rotulos_normalizados` pega.

Os testes leem o parquet ja gerado — nao batem na rede. Fonte fora do ar nao
pode quebrar a suite, e o dado versionado e o que a API serve de qualquer
forma.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.ingest import ibge_bdia as bdia

INTERIM = Path(__file__).resolve().parents[1] / "data" / "interim"

# Area do RS pelo IBGE: 281.707 km2. A grade recortada por municipio devolve
# ~268.6 mil — a diferenca e a agua costeira e lagunar que fica fora do
# poligono municipal na malha. A faixa e larga de proposito: o teste existe
# para pegar zero e pegar o estado inteiro em dobro, nao para auditar area.
AREA_MIN_KM2 = 250_000
AREA_MAX_KM2 = 290_000


def _ler(nome: str) -> pd.DataFrame:
    caminho = INTERIM / nome
    if not caminho.exists():
        pytest.skip(f"{nome} ausente — rode `python -m src.ingest.ibge_bdia`")
    return pd.read_parquet(caminho)


@pytest.fixture(scope="module", params=list(bdia.CAMADAS))
def camada(request):
    c = bdia.CAMADAS[request.param]
    return c, _ler(c.saida)


def test_cobre_os_497_municipios(camada):
    _, df = camada
    assert df.cod_mun.nunique() == 497


def test_area_bate_com_o_estado(camada):
    """A guarda contra a geometria nula: o modo de falha e sair zerado."""
    _, df = camada
    total = float(df[~df.sem_mapeamento].km2.sum())
    assert AREA_MIN_KM2 < total < AREA_MAX_KM2, total


def test_fracoes_somam_um_por_municipio(camada):
    _, df = camada
    soma = df.groupby("cod_mun").frac.sum()
    assert soma.between(0.999, 1.001).all()


def test_quase_nada_fica_sem_mapeamento(camada):
    """Fracao sem classe alta significa recorte errado, nao mapa incompleto."""
    _, df = camada
    vazio = df[df.sem_mapeamento].groupby("cod_mun").frac.sum()
    assert float(vazio.max() if len(vazio) else 0.0) < 0.25


def test_rotulos_normalizados(camada):
    """Nenhum rotulo com quebra de linha ou espaco duplo sobrevive a chave."""
    _, df = camada
    for coluna in df.columns:
        if df[coluna].dtype != object:
            continue
        valores = [v for v in df[coluna].dropna().unique() if isinstance(v, str)]
        for v in valores:
            assert "\n" not in v, (coluna, repr(v))
            assert "  " not in v, (coluna, repr(v))


def test_cruzado_tem_as_tres_camadas():
    df = _ler(bdia.SAIDA_CRUZADO)
    assert df.cod_mun.nunique() == 497
    for prefixo in ("pedo_", "vege_", "geom_"):
        assert any(c.startswith(prefixo) for c in df.columns), prefixo
    total = float(df.km2.sum())
    assert AREA_MIN_KM2 < total < AREA_MAX_KM2


def test_cruzado_preserva_a_combinacao_e_nao_a_media():
    """O cruzamento existe para nao supor independencia entre solo e cobertura.

    Se um municipio sair com uma linha so, ou se toda linha de um solo tiver
    a mesma cobertura, o cruzamento degenerou e o CN volta a ser media.
    """
    df = _ler(bdia.SAIDA_CRUZADO)
    por_mun = df.groupby("cod_mun").size()
    assert por_mun.median() >= 5
    # E o mesmo solo aparece sob coberturas diferentes pelo estado — que e
    # justamente a informacao que a suposicao de independencia destruiria.
    combos = df.groupby("pedo_ordem").vege_legenda_2.nunique(dropna=False)
    assert (combos > 1).any()
