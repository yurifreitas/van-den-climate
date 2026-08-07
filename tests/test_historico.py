"""Historia longa da chuva — o primeiro contato com o alvo do projeto.

Este arquivo guarda duas coisas diferentes.

A primeira e mecanica: o `.dly` do GHCN traz precipitacao em DECIMOS de
milimetro. Esquecer a divisao por 10 produz uma serie dez vezes maior que a
realidade — plausivel o bastante para passar num grafico e catastrofica num
percentil. `test_dly_converte_decimos_para_milimetros` trava isso.

A segunda e de disciplina: este dominio E contato com o alvo (ADR-004). O
teste `test_meta_declara_contato_com_o_alvo` existe para que a consequencia
— feature_blocks.yaml congelado de fato — nao possa sumir do payload numa
refatoracao distraida.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.ingest.ghcn_rs import parse_dly
from src.risk import historico as h

# Linha no formato real: ID(11) ANO(4) MES(2) ELEM(4), depois 31 blocos de
# EXATAMENTE 8 caracteres — valor(5) + MFLAG(1) + QFLAG(1) + SFLAG(1).
# Aqui MFLAG e QFLAG ficam em branco (dado bom) e SFLAG e 'I'.
# Bloco de 9 caracteres desalinha tudo a partir do segundo dia: foi assim que
# a primeira versao deste teste quebrou, e o parser estava certo.
def _bloco(valor: int) -> str:
    return f"{valor:5d}  I"


LINHA = (
    "BR002956005193401PRCP"
    + "".join(_bloco(v) for v in [0, 84, 0, 0, 0, 0, 0, 0, 0, 0])
    + "".join(_bloco(-9999) for _ in range(21))
)


def test_dly_converte_decimos_para_milimetros():
    df = parse_dly(LINHA, "BR002956005")
    assert len(df) == 10  # os 21 -9999 sao descartados
    assert df["prcp_mm"].max() == pytest.approx(8.4)  # 84 decimos = 8,4 mm
    assert df["prcp_mm"].min() == 0.0


def test_dly_descarta_ausente_em_vez_de_virar_zero():
    """-9999 tem de sumir da serie, nunca virar 0 mm de chuva."""
    df = parse_dly(LINHA, "BR002956005")
    assert not (df["prcp_mm"] < 0).any()
    assert len(df) < 31


# ---------------------------------------------------------------------------
# Trio da ADR-002
# ---------------------------------------------------------------------------
def test_trio_usa_limiar_de_dia_umido():
    """Dia com 0,5 mm nao e dia umido: o limiar da OMM e 1 mm."""
    serie = pd.Series([0.0, 0.5, 1.0, 20.0])
    t = h._trio(serie)
    assert t["freq_dias_umidos"] == pytest.approx(0.5)  # 1.0 e 20.0
    assert t["intensidade_mm"] == pytest.approx(10.5)


def test_p95_e_sobre_todos_os_dias_nao_so_os_umidos():
    """Condicionar em dia umido apagaria a informacao de quantos dias secos
    separam os eventos — que e parte do alvo."""
    serie = pd.Series([0.0] * 90 + [50.0, 100.0])
    t = h._trio(serie)
    # com 92 dias e so 2 chuvosos, o p95 fica baixo; se fosse so sobre umidos
    # ficaria proximo de 100
    assert t["p95_mm"] < 60


# ---------------------------------------------------------------------------
# Disciplina do projeto
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def resultado():
    if not h.DIARIO.exists():
        pytest.skip("serie GHCN nao ingerida — rode `python -m src.ingest.ghcn_rs`")
    return h.calcular()


def test_meta_declara_contato_com_o_alvo(resultado):
    """Se este campo sumir, some junto o aviso de que o experimento congelou."""
    texto = resultado.meta["contato_com_alvo"].lower()
    assert "alvo" in texto
    assert "feature_blocks" in texto


def test_limites_declaram_o_fim_da_serie(resultado):
    txt = " ".join(resultado.meta["limites"]).lower()
    assert "1999" in txt or "operacional" in txt
    assert "homogeneiza" in txt


def test_nenhum_modelo_foi_ajustado(resultado):
    """O modulo e descritivo. Se alguem adicionar ajuste, o limite tem de mudar
    junto — e este teste obriga a passar por aqui."""
    assert any("descritiva" in l.lower() for l in resultado.meta["limites"])


# ---------------------------------------------------------------------------
# Contrato do composto
# ---------------------------------------------------------------------------
def test_temporada_incompleta_nao_entra(resultado):
    assert h.MIN_DIAS <= h.DIAS_OND
    assert (resultado.por_estacao_ano["n_dias"] >= h.MIN_DIAS).all()


def test_fases_cobrem_a_serie(resultado):
    fases = set(resultado.por_ano["fase"])
    assert {"El Nino", "Neutro", "La Nina"} <= fases


def test_deslocamento_traz_intervalo_e_veredito(resultado):
    d = resultado.composto.get("deslocamento_elnino_vs_neutro")
    assert d, "deslocamento ausente"
    for metrica, v in d.items():
        assert len(v["ic90"]) == 2
        assert v["ic90"][0] <= v["delta"] <= v["ic90"][1], metrica
        # o veredito tem de ser coerente com o proprio intervalo
        esperado = v["ic90"][0] > 0 or v["ic90"][1] < 0
        assert v["separa_de_zero"] is esperado, metrica


def test_ordenacao_das_fases_e_coerente(resultado):
    """El Nino > Neutro > La Nina no total da estacao.

    Nao e um teste de hipotese — e um teste de COERENCIA. Se a ordem se
    inverter, o mais provavel e erro de sinal no ONI ou no join, nao uma
    descoberta climatologica.
    """
    f = resultado.composto["fases"]
    assert f["El Nino"]["total_mm"]["media"] > f["Neutro"]["total_mm"]["media"]
    assert f["Neutro"]["total_mm"]["media"] > f["La Nina"]["total_mm"]["media"]


def test_bootstrap_e_deterministico():
    """Semente fixa: o numero na tela nao pode mudar entre recargas."""
    por_ano = pd.DataFrame({
        "ano": range(2000, 2030),
        "fase": ["El Nino"] * 10 + ["Neutro"] * 10 + ["La Nina"] * 10,
        "freq_dias_umidos": np.linspace(0.1, 0.4, 30),
        "intensidade_mm": np.linspace(10, 30, 30),
        "p95_mm": np.linspace(15, 45, 30),
        "total_mm": np.linspace(200, 600, 30),
    })
    a = h._composto_por_fase(por_ano)
    b = h._composto_por_fase(por_ano)
    assert a == b
