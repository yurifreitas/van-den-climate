"""Rota /terreno — o envelope, e por que ele e `modeled` inteiro.

A tentacao desta camada e especifica e vale um teste proprio: a origem do dado
e um MAPA do IBGE, e mapa parece medicao. Mas nada do que sai daqui e o mapa —
e o mapa depois de tres traducoes (ordem do SiBCS para grupo hidrologico, par
(grupo, cobertura) para Curve Number, serie diaria para chuva de projeto por
Gumbel). Selar isso como `measured` seria lavagem de proveniencia com a melhor
das intencoes, e e exatamente o que a regra 2 do projeto existe para impedir.

O segundo teste guarda a outra fronteira: `concentracao` cruza as duas camadas
e a leitura obvia seria "indice combinado de risco de terreno". Nao e — e a
intersecao de dois decis, e o criterio viaja escrito no payload para que
ninguem precise adivinhar.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def payload():
    client = TestClient(app)
    r = client.get("/api/v1/terreno", params={"limite": 20})
    if r.status_code == 503:
        pytest.skip("camada de terreno nao ingerida")
    assert r.status_code == 200, r.text
    return r.json()


def test_envelope_e_modelado(payload):
    assert payload["provenance"]["basis"] == "modeled"
    assert "ibge_bdia" in payload["provenance"]["source_ids"]


def test_as_duas_camadas_declaram_limites(payload):
    for camada in ("hidrologia", "degradacao"):
        limites = payload[camada]["limites"]
        assert len(limites) >= 5, camada
        assert all(isinstance(x, str) and len(x) > 40 for x in limites), camada


def test_limite_de_pagina_respeitado(payload):
    assert len(payload["hidrologia"]["municipios"]) == 20
    assert payload["hidrologia"]["n_total"] >= 490


def test_escoamento_vem_em_par_seco_e_umido(payload):
    """O desastre acontece na terceira chuva. Publicar so a media mente."""
    m = payload["hidrologia"]["municipios"][0]
    assert m["eventos"], m["municipio"]
    for e in m["eventos"]:
        assert e["escoamento_mm_solo_umido"] >= e["escoamento_mm"]
        assert e["escoamento_mm"] <= e["p24h_mm"]


def test_resposta_e_ordinal_nunca_minutos(payload):
    """Sem talvegue nem declividade medida nao existe tempo de concentracao."""
    for m in payload["hidrologia"]["municipios"]:
        assert m["resposta"] in {"muito rapida", "rapida", "moderada", "lenta", None}


def test_concentracao_declara_que_nao_e_indice(payload):
    c = payload["concentracao"]
    assert "intersecao" in c["criterio"].lower()
    assert "indice composto" in c["criterio"].lower()
    for m in c["municipios"]:
        assert m["cn2"] >= c["limiar_cn2"]


def test_degradacao_publica_area_medida_junto_do_indice(payload):
    """Se o indice cair, estes numeros continuam de pe."""
    resumo = payload["degradacao"]["resumo"]
    assert resumo["km2_uso_intensivo_em_declive_rs"] > 0
    assert resumo["p_assumido"] == 1.0
    m = payload["degradacao"]["municipios"][0]
    assert "km2_uso_intensivo_em_declive" in m
    assert "RS" in m["classe"]
