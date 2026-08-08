"""Pessoal, voluntariado e auxilio mutuo.

O teste central e `test_recusa_nao_vira_zero_servidor`. As contagens do MUNIC
vem como texto e trazem '-' e 'Recusa'. Converter isso para 0 produziria
"prefeitura sem funcionarios" — numero absurdo o bastante para nao levantar
suspeita num agregado, e catastrofico num indicador per capita.

O segundo e `test_voluntariado_so_dispara_com_quadro_fragil`: 235 municipios
estao a mais de 60 km de uma brigada voluntaria, e a maioria nao precisa de
uma. Distancia sozinha viraria recomendacao em massa sem lastro.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.risk import pessoal, plano


@pytest.fixture(scope="module")
def p():
    if not pessoal.MUNIC_PARQUET.exists():
        pytest.skip("base municipal nao ingerida — rode `python -m src.ingest.ibge_rs`")
    return pessoal.build()


# ---------------------------------------------------------------------------
# As duas regressoes
# ---------------------------------------------------------------------------
def test_recusa_nao_vira_zero_servidor(p):
    """Quadro ausente e None, nunca 0."""
    for r in p.rows:
        total = r["quadro"]["total"]
        if total is not None:
            assert total > 0, f"{r['municipio']}: quadro zerado e implausivel"
        else:
            # ausente tem de propagar: sem total nao ha razao nem basis
            assert r["quadro"]["por_mil_hab"] is None
            assert r["quadro"]["basis"] is None


def test_voluntariado_so_dispara_com_quadro_fragil():
    """Distancia sozinha nao gera acao — precisa de fragilidade junto."""
    base = {"quadro": {"quadro_fragil": False, "total": 500}, "faltou_pessoal_em_2024": False,
            "voluntariado": {"km_brigada_mais_proxima": 200.0}}
    assert plano._sem_voluntariado({}, None, None, base) is None

    fragil = {**base, "quadro": {"quadro_fragil": True, "total": 500}}
    assert plano._sem_voluntariado({}, None, None, fragil) is not None

    perto = {**fragil, "voluntariado": {"km_brigada_mais_proxima": 20.0}}
    assert plano._sem_voluntariado({}, None, None, perto) is None


# ---------------------------------------------------------------------------
# Contrato
# ---------------------------------------------------------------------------
def test_cobre_os_497(p):
    assert p.resumo["n_municipios"] == 497
    assert len(p.rows) == 497


def test_fragilidade_e_fracao_valida(p):
    for r in p.rows:
        f = r["quadro"]["frac_sem_estabilidade"]
        if f is not None:
            assert 0.0 <= f <= 1.0, r["municipio"]


def test_quadro_fragil_respeita_o_limiar(p):
    for r in p.rows:
        q = r["quadro"]
        if q["frac_sem_estabilidade"] is None:
            assert q["quadro_fragil"] is None
        else:
            esperado = q["frac_sem_estabilidade"] >= pessoal.LIMIAR_FRAGILIDADE
            assert q["quadro_fragil"] is esperado, r["municipio"]


def test_resumo_declara_que_per_capita_nao_mede_suficiencia(p):
    nota = p.resumo["servidores_por_mil"]["nota"].lower()
    assert "nao e medida de suficiencia" in nota or "não e medida" in nota
    assert "indivisibilidade" in nota


def test_limites_declaram_o_escopo_do_quadro(p):
    txt = " ".join(p.resumo["limites"]).lower()
    assert "direta" in txt          # nao inclui indireta nem terceirizado
    assert "leitura declarada" in txt  # a ponderacao de fragilidade e editorial
    assert "defesa civil" in txt    # nao ha efetivo de defesa civil no MUNIC


# ---------------------------------------------------------------------------
# Voluntariado e auxilio mutuo
# ---------------------------------------------------------------------------
def test_modelo_existente_nomeia_a_serra(p):
    """A estrategia proposta e replicar arranjo local, nao importar modelo."""
    txt = p.resumo["voluntariado"]["modelo_existente"].lower()
    assert "serra" in txt
    assert "nao e preciso importar" in txt or "não é preciso importar" in txt


def test_brigadas_sao_identificadas_por_heuristica(p):
    """A identificacao e por nome; nao ha campo 'voluntario' em nenhuma base."""
    for r in p.rows:
        assert "heuristica" in r["voluntariado"]["nota"]


def test_auxilio_mutuo_respeita_o_raio():
    from src.risk.municipal import MUNIC_PARQUET, build_table

    if not MUNIC_PARQUET.exists():
        pytest.skip("base municipal nao ingerida")
    pares = pessoal.auxilio_mutuo(build_table(1.39).rows, limite=50)
    for a in pares:
        assert a["motivos"], a["municipio"]
        assert a["vizinhos_com_folga"], a["municipio"]
        for v in a["vizinhos_com_folga"]:
            assert v["km"] <= pessoal.RAIO_AUXILIO_KM
            assert v["cod_mun"] != a["cod_mun"]


def test_auxilio_mutuo_nao_afirma_capacidade_ociosa():
    """O docstring precisa dizer que 'folga' e ausencia de sinal de
    fragilidade, nao medicao — a diferenca muda como a sugestao e lida."""
    doc = pessoal.auxilio_mutuo.__doc__ or ""
    assert "nunca para afirmar" in doc


def test_tri_converte_recusa_para_none():
    from src.ingest.ibge_rs import _tri

    assert _tri("Sim") is True
    assert _tri("Não") is False
    for ausente in ("-", "Recusa", "Não sabe informar", "Não informou", None):
        assert _tri(ausente) is None, ausente


def test_contagens_do_munic_aceitam_recusa():
    """pd.to_numeric com coerce e o que impede 'Recusa' de virar 0."""
    s = pd.Series(["206", "-", "Recusa", "14"])
    out = pd.to_numeric(s, errors="coerce")
    assert out.isna().sum() == 2
    assert out.dropna().tolist() == [206.0, 14.0]
