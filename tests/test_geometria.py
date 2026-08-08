"""Geometria do sistema — atrator, recorrencia, fractal, distancia.

Este arquivo guarda tres armadilhas que ja morderam durante a analise. Todas
produzem NUMERO PLAUSIVEL a partir de metodo errado, que e a unica forma
perigosa de errar aqui: um NaN alguem percebe, um 3.0 no lugar de 0.12 vai
para o relatorio.

1. `test_p_nao_pode_ser_menor_que_o_piso` — com 20 surrogates o menor p
   alcancavel e 1/21 = 0,048. Reportar "p = 0,048" ali e reportar o PISO DE
   RESOLUCAO do teste, nao a forca da evidencia. Os dois coincidem
   numericamente e significam coisas opostas.

2. `test_multifractal_q_negativo_e_armadilha` — em serie com muitos zeros o
   lado de q negativo mede o descarte de segmentos, nao a dinamica. Deu
   largura 3,0 onde a resposta e ~0,12.

3. `test_teste_de_regime_detecta_recorte_invalido` — mascarar agua pela malha
   municipal remove 84% dela (Patos e Mirim ficam fora), justamente o corpo
   compacto que o teste procurava. Sem a checagem de cobertura, o teste
   "refutaria" a classificacao de regime por artefato.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.represent import geometria as g


# ---------------------------------------------------------------------------
# Criterios de admissao
# ---------------------------------------------------------------------------
def test_ruelle_e_smith_discordam_e_smith_e_o_duro():
    """Os dois criterios existem juntos porque a distancia entre eles E a
    incerteza. Se Smith virar o permissivo, algo foi invertido."""
    n = 918
    d = 3.08
    assert d < g.ruelle_max_dim(n)          # Ruelle aceita
    assert g.smith_min_pontos(d) > n        # Smith recusa
    assert g.smith_min_pontos(d) > 50_000   # e recusa por ordem de grandeza


def test_smith_cresce_exponencialmente():
    assert g.smith_min_pontos(3) / g.smith_min_pontos(2) == pytest.approx(42.0)


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------
def test_embutir_forma_correta():
    x = np.arange(100, dtype=float)
    y = g.embutir(x, m=3, tau=5)
    assert y.shape == (100 - 2 * 5, 3)
    # a primeira coluna e a serie original truncada
    assert y[0, 0] == 0.0 and y[0, 1] == 5.0 and y[0, 2] == 10.0


def test_embutir_recusa_serie_curta():
    with pytest.raises(ValueError):
        g.embutir(np.arange(10, dtype=float), m=5, tau=5)


def test_informacao_mutua_e_maxima_no_lag_zero():
    rng = np.random.default_rng(1)
    x = np.cumsum(rng.normal(size=600))
    im = g.informacao_mutua(x, lag_max=24)
    assert im[0] == max(im)


def test_falsos_vizinhos_desabam_em_serie_deterministica():
    """Serie de Henon: 2 dimensoes bastam, e a fracao tem de cair."""
    n = 2000
    x = np.zeros(n)
    y = np.zeros(n)
    for i in range(1, n):
        x[i] = 1 - 1.4 * x[i - 1] ** 2 + y[i - 1]
        y[i] = 0.3 * x[i - 1]
    f = g.falsos_vizinhos(x[500:], tau=1, m_max=5)
    assert f[0] > f[-1]
    assert min(f) < 0.1


# ---------------------------------------------------------------------------
# Recorrencia e o piso de p
# ---------------------------------------------------------------------------
def test_rqa_separa_deterministico_de_ruido():
    """DET alto em sistema deterministico, baixo em ruido branco. Se este
    teste cair, a RQA parou de medir o que diz medir."""
    rng = np.random.default_rng(2)
    t = np.linspace(0, 60 * np.pi, 1200)
    senoide = np.sin(t) + 0.3 * np.sin(2.7 * t)
    ruido = rng.normal(size=1200)
    det_sin = g.rqa(g.embutir(senoide, 3, 8))["determinismo"]
    det_rui = g.rqa(g.embutir(ruido, 3, 8))["determinismo"]
    assert det_sin > det_rui
    assert det_sin > 0.9


def test_p_nao_pode_ser_menor_que_o_piso():
    """A ARMADILHA 1. Com n surrogates o menor p possivel e 1/(n+1)."""
    rng = np.random.default_rng(3)
    x = np.cumsum(rng.normal(size=400))
    for n_surr in (20, 50):
        r = g.teste_nao_linearidade(x, m=3, tau=5, n_surr=n_surr)
        # o modulo arredonda para 4 casas ao reportar
        assert r["piso_de_p"] == pytest.approx(1.0 / (n_surr + 1), abs=1e-4)
        assert r["p_unilateral"] >= r["piso_de_p"]


def test_iaaft_preserva_a_distribuicao():
    """E o que distingue IAAFT do surrogate de fase: o histograma sobrevive.

    Surrogate de fase impoe amplitude gaussiana; se a serie nao for gaussiana,
    parte da diferenca contra o observado vem da distribuicao e o teste
    rejeita a hipotese errada."""
    rng = np.random.default_rng(4)
    x = rng.exponential(size=512)  # bem nao gaussiana
    s = g.surrogate_iaaft(x, rng)
    assert np.allclose(np.sort(x), np.sort(s))
    assert not np.allclose(x, s)


# ---------------------------------------------------------------------------
# Fractal
# ---------------------------------------------------------------------------
def test_dfa_recupera_hurst_de_ruido_branco():
    """Ruido branco tem H = 0,5. Este teste pegou um vies real: com escala
    maxima em n/4 o estimador devolvia 0,44 — sobravam 4 segmentos na maior
    escala e a media instavel torcia a reta. Media sobre sementes para nao
    depender de sorte de uma so."""
    hs = [g.dfa(np.random.default_rng(s).normal(size=8000))["hurst"] for s in range(6)]
    assert 0.47 < float(np.mean(hs)) < 0.53


def test_dfa_recusa_serie_curta():
    assert g.dfa(np.arange(100, dtype=float))["hurst"] is None


def test_multifractal_q_negativo_e_armadilha():
    """A ARMADILHA 2. Serie com muitos zeros infla a largura pelo lado de q<0.

    O diagnostico tem de mostrar que os dois lados discordam, e apontar o
    positivo como o publicavel."""
    rng = np.random.default_rng(6)
    # chuva sintetica: 60% de dias secos
    x = np.where(rng.random(20000) < 0.6, 0.0, rng.exponential(8, 20000))
    d = g.diagnostico_multifractal(x)
    assert d["frac_zeros"] > 0.5
    assert "positivo" in d["veredito"].lower()
    lp = d["lado_q_positivo"].get("largura")
    ln = d["lado_q_negativo"].get("largura")
    if lp is not None and ln is not None:
        # o lado negativo infla; se algum dia parar de inflar, o comentario
        # do modulo precisa mudar junto
        assert ln > lp


# ---------------------------------------------------------------------------
# Box counting
# ---------------------------------------------------------------------------
def test_box_counting_de_quadrado_cheio_tende_a_2():
    m = np.ones((256, 256), dtype=bool)
    assert g.box_counting(m)["dimensao"] == pytest.approx(2.0, abs=0.05)


def test_box_counting_de_linha_tende_a_1():
    m = np.zeros((256, 256), dtype=bool)
    m[128, :] = True
    assert g.box_counting(m)["dimensao"] == pytest.approx(1.0, abs=0.1)


def test_box_counting_recusa_mascara_pequena():
    m = np.zeros((64, 64), dtype=bool)
    m[0, :10] = True
    assert g.box_counting(m)["dimensao"] is None


# ---------------------------------------------------------------------------
# O teste que pode derrubar — e a checagem que impede a derrubada errada
# ---------------------------------------------------------------------------
def test_teste_de_regime_detecta_recorte_invalido():
    """A ARMADILHA 3. Se a mascara cobre menos da metade da agua, o resultado
    nao pode ser lido como refutacao."""
    r = g.testar_regime_pela_geometria()
    if not r.get("disponivel"):
        pytest.skip("grade do JRC ou classificacao de bacia ausente")
    cob = r["cobertura_da_agua"]["fracao"]
    if cob < 0.5:
        assert r["teste_valido"] is False
        assert r["confirma_classificacao"] is None
        assert "INVALIDO" in r["veredito"]
    else:
        assert r["confirma_classificacao"] is not None


# ---------------------------------------------------------------------------
# A fronteira do projeto
# ---------------------------------------------------------------------------
def test_metodos_recusados_dizem_o_n_que_exigiriam():
    """Recusa sem numero e preconceito. Cada recusa nomeia o que faltou."""
    assert len(g.RECUSADOS) >= 4
    for r in g.RECUSADOS:
        assert r["exigiria"] and r["temos"] and r["veredito"]
        assert any(p in r["veredito"] for p in ("RECUSADO", "PARCIAL", "NAO APLICAVEL"))


def test_lyapunov_e_tda_seguem_recusados():
    """ADR-008 continua valendo. Se alguem os reintroduzir, isto cai."""
    nomes = " ".join(r["metodo"] for r in g.RECUSADOS).lower()
    assert "lyapunov" in nomes
    assert "tda" in nomes or "topologica" in nomes


def test_modulo_declara_que_nao_toca_o_alvo():
    """Se algum numero daqui virar feature, o experimento morre (ADR-042)."""
    doc = (g.__doc__ or "").lower()
    assert "feature_blocks" in doc
    assert "adr-042" in doc or "congelado" in doc
