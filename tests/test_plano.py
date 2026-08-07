"""Plano de acao preventiva.

O teste que da nome ao arquivo e `test_toda_acao_carrega_evidencia`. O plano
so vale enquanto cada item puder ser rastreado ate a linha de dado que o
disparou: uma lista de recomendacoes sem evidencia ao lado e opiniao com
aparencia de sistema, e ninguem consegue contestar item por item.

O segundo em importancia e `test_nenhuma_acao_inferida`: se o campo que
dispara a acao esta ausente, a acao NAO aparece. Nao existe "provavelmente
necessario" nesta lista — ausencia de dado nunca vira recomendacao.
"""
from __future__ import annotations

import pytest

from src.risk import plano


@pytest.fixture(scope="module")
def p():
    from src.risk.municipal import MUNIC_PARQUET

    if not MUNIC_PARQUET.exists():
        pytest.skip("base municipal nao ingerida — rode `python -m src.ingest.ibge_rs`")
    return plano.build(oni=1.39)


# ---------------------------------------------------------------------------
# Rastreabilidade
# ---------------------------------------------------------------------------
def test_toda_acao_carrega_evidencia(p):
    for m in p["municipios"]:
        for a in m["acoes"]:
            assert a["evidencia"], f"{m['municipio']}/{a['id']} sem evidencia"
            assert a["fonte"], f"{m['municipio']}/{a['id']} sem fonte"
            assert a["basis"] == "measured"


def test_evidencia_nomeia_a_base(p):
    """A evidencia comeca pelo nome da base — quem le sabe onde conferir."""
    prefixos = ("MUNIC 2024", "CNES", "JRC")
    for m in p["municipios"]:
        for a in m["acoes"]:
            assert a["evidencia"].startswith(prefixos), a["evidencia"]


def test_nenhuma_acao_inferida():
    """Municipio sem nenhum campo preenchido nao gera acao nenhuma."""
    vazio = {"cod_mun": 4300000, "municipio": "Vazio", "componentes": {}, "aguas": None}
    for acao in plano.ACOES:
        assert acao.gatilho(vazio, None) is None, f"{acao.id} disparou sem dado"


def test_gatilho_distingue_nao_de_ausente():
    """`plano_contingencia: None` (nao respondeu) nao pode gerar a mesma acao
    que `False` (declarou nao ter). Ausencia nao e diagnostico."""
    base = {"cod_mun": 1, "municipio": "T", "aguas": None}
    sem = {**base, "componentes": {"deficit_prevencao": {"detalhe": {"plano_contingencia": False}}}}
    nulo = {**base, "componentes": {"deficit_prevencao": {"detalhe": {"plano_contingencia": None}}}}
    assert plano._sem_plano(sem, None) is not None
    assert plano._sem_plano(nulo, None) is None


# ---------------------------------------------------------------------------
# Estrutura do plano
# ---------------------------------------------------------------------------
def test_cobre_os_497_e_conta_certo(p):
    assert p["n_municipios"] == 497
    assert p["n_acoes_total"] == sum(len(m["acoes"]) for m in p["municipios"])
    assert p["n_imediatas_total"] == sum(m["n_imediatas"] for m in p["municipios"])
    assert p["n_com_acao"] == sum(1 for m in p["municipios"] if m["acoes"])


def test_horizontes_sao_so_os_dois_declarados(p):
    for m in p["municipios"]:
        for a in m["acoes"]:
            assert a["horizonte"] in ("imediato", "estrutural")
            assert a["esforco"] in ("baixo", "medio", "alto")


def test_agregado_bate_com_o_detalhe(p):
    for agg in p["por_acao"]:
        contados = sum(1 for m in p["municipios"] if any(a["id"] == agg["id"] for a in m["acoes"]))
        assert agg["n_municipios"] == contados, agg["id"]


def test_ordenacao_poe_risco_primeiro(p):
    scores = [m["score"] for m in p["municipios"] if m["score"] is not None]
    assert scores == sorted(scores, reverse=True)


def test_municipio_sem_base_nao_encabeca_o_plano(p):
    """Mesma regra do indice: ausencia de dado nao promove ninguem."""
    assert p["municipios"][0]["score"] is not None


# ---------------------------------------------------------------------------
# Honestidade declarada
# ---------------------------------------------------------------------------
def test_limites_negam_engenharia_e_custo(p):
    txt = " ".join(p["limites"]).lower()
    assert "engenharia" in txt
    assert "custo" in txt
    assert "editorial" in txt


def test_esforco_e_declarado_como_editorial(p):
    assert any("editorial" in l.lower() for l in p["limites"])


def test_plano_declara_que_nao_substitui_defesa_civil(p):
    assert any("defesa civil" in l.lower() for l in p["limites"])


def test_cenario_invalido_falha_alto():
    with pytest.raises(ValueError, match="cenario desconhecido"):
        plano.build("chute", 1.0)


def test_acoes_tem_ids_unicos():
    ids = [a.id for a in plano.ACOES]
    assert len(ids) == len(set(ids))
