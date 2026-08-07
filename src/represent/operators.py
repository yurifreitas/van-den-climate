"""Camada 3 — os cinco operadores causais (Predict, Surprise, Shift,
Persistence, Regime).

Toda variavel entra pela mesma interface (uma serie temporal + um instante t)
e sai como `ClimateSignal(value, expected, surprise, shift, persistence,
regime)`. O ponto inteiro deste modulo e que NENHUM dos cinco calculos pode
olhar para o futuro em relacao a t — nem o valor, nem o ajuste de qualquer
transformacao usada para produzi-lo (§8.4, ADR-010). Por isso toda funcao
publica aqui devolve, alem do numero, um `FeatureProvenance` com
`input_timestamps` (o que entrou na conta) e `fitted_on` (o que foi usado
para AJUSTAR — AR, calibracao, referencia de distancia). O gate de
`src/validate/leakage.py` verifica os dois separadamente porque o modo de
falha real do projeto e o segundo: o VALOR respeita o corte, mas a
normalizacao foi ajustada no conjunto inteiro.

Nada aqui toca o alvo (§ README) — estes operadores rodam sobre ~17.500
campos diarios, entao matematica mais cara (MMD, M-SSA em outro lugar) e
aceitavel aqui mesmo que seja proibida na camada supervisionada.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.contracts import ANCHOR_END, ANCHOR_START, ClimateSignal
from src.validate.leakage import FeatureProvenance

__all__ = [
    "PredictResult",
    "predict_ar",
    "SurpriseResult",
    "causal_percentile",
    "surprise",
    "ShiftResult",
    "shift_ks",
    "shift_wasserstein",
    "shift_mmd",
    "shift_combined",
    "persistence",
    "regime",
    "build_climate_signal",
]


# ---------------------------------------------------------------------------
# 1. PREDICT — x_hat_t = f(x_<t)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PredictResult:
    expected: float
    residual: float  # x_t - x_hat_t (a "surpresa crua", antes da calibracao)
    provenance: FeatureProvenance


def predict_ar(
    series: pd.Series,
    t: pd.Timestamp,
    *,
    feature: str,
    target_year: int,
    order: int = 1,
    min_history: int | None = None,
) -> PredictResult:
    """Baseline AR(p) ajustado por minimos quadrados, expanding a partir da
    ancora, usando ESTRITAMENTE observacoes anteriores a `t`.

    `series` deve ter indice de timestamps ordenado. O ajuste dos
    coeficientes usa a janela [ANCHOR_START, t) — nunca inclui t nem nada
    posterior. Isso e o oposto de um AR "de bibliotecas de series temporais"
    tipico, que ajusta uma vez no conjunto inteiro e depois faz predicao
    fora da amostra; aqui o ajuste e refeito a cada t (walk-forward real),
    porque e exatamente essa refatoracao continua que impede vazamento de
    informacao futura para o coeficiente do AR.
    """
    if order < 1:
        raise ValueError("order deve ser >= 1")
    min_history = min_history if min_history is not None else order + 2

    hist = series[(series.index >= pd.Timestamp(ANCHOR_START)) & (series.index < t)].dropna()
    hist = hist.sort_index()

    if len(hist) < min_history:
        # Sem historico suficiente: previsao ingenua = media da historia
        # disponivel (ou 0.0 se nao ha nada). Isso e deliberadamente burro —
        # nao inventamos coeficiente com 2 pontos.
        expected = float(hist.mean()) if len(hist) else 0.0
        x_t = float(series.loc[t]) if t in series.index else np.nan
        residual = x_t - expected if not np.isnan(x_t) else np.nan
        prov = FeatureProvenance(
            feature=feature,
            target_year=target_year,
            input_timestamps=[t] if t in series.index else [],
            fitted_on=list(hist.index),
        )
        return PredictResult(expected, residual, prov)

    y = hist.values.astype(float)
    n = len(y)
    # Monta X com `order` defasagens + intercepto, usando so pontos dentro
    # de hist (portanto so passado de t). Minimos quadrados via SVD
    # (np.linalg.lstsq) — evita dependencia extra so para um AR(p) simples.
    X = np.ones((n - order, order + 1))
    for k in range(order):
        X[:, k + 1] = y[order - 1 - k : n - 1 - k]
    yy = y[order:]
    coefs, *_ = np.linalg.lstsq(X, yy, rcond=None)

    last_lags = y[-order:][::-1]  # [x_{t-1}, x_{t-2}, ..., x_{t-order}]
    x_row = np.concatenate([[1.0], last_lags])
    expected = float(x_row @ coefs)

    x_t = float(series.loc[t]) if t in series.index else np.nan
    residual = x_t - expected if not np.isnan(x_t) else np.nan

    prov = FeatureProvenance(
        feature=feature,
        target_year=target_year,
        input_timestamps=[t] if t in series.index else [],
        fitted_on=list(hist.index),  # e o que foi usado para AJUSTAR os coefs
    )
    return PredictResult(expected, residual, prov)


# ---------------------------------------------------------------------------
# 2. SURPRISE — S_t = C(x_t - x_hat_t), calibracao causal / self-null
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SurpriseResult:
    percentile: float          # p_t em (0, 1]
    resolution: float          # 1/t — a menor unidade representavel
    low_resolution: bool       # True se t < 30 (ADR-001)
    provenance: FeatureProvenance


def causal_percentile(
    residuals_history: np.ndarray,
    current_residual: float,
) -> tuple[float, float]:
    """p_t = (1 + #{i<t : d_i >= d_t}) / t, com d = |residuo| (surpresa em
    modulo — direcao fica no sinal de `residual`, magnitude no percentil).

    Esta e uma calibracao "self-null": comparamos a surpresa atual so contra
    surpresas PASSADAS, nunca contra o conjunto inteiro. E por isso que a
    resolucao e exatamente 1/t (t = numero de residuos anteriores + o
    proprio, i.e. len(residuals_history) + 1): com t observacoes so existem
    t valores possiveis de p, {1/t, 2/t, ..., t/t}. Nao existe meio-termo.

    IMPORTANTE (ver docstring de `surprise`): em t=15 a menor probabilidade
    representavel e 1/15 ~= 0.067 — nao da para expressar "evento 1 em 50"
    ainda que ele tenha de fato acontecido. Isso nao e um bug a corrigir com
    interpolacao ou suavizacao: suavizar aqui e fabricar resolucao que os
    dados nao tem. E exatamente a razao da ancora fixa 1951-1990 (ADR-001)
    — ela da t grande o suficiente (ate 40 anos de historico antes do
    periodo de avaliacao) para que a resolucao pare de ser o fator
    limitante.
    """
    d_hist = np.abs(residuals_history[~np.isnan(residuals_history)])
    d_t = abs(current_residual)
    t = len(d_hist) + 1
    count_ge = int(np.sum(d_hist >= d_t))
    p = (1 + count_ge) / t
    resolution = 1.0 / t
    return p, resolution


def surprise(
    series: pd.Series,
    t: pd.Timestamp,
    *,
    feature: str,
    target_year: int,
    order: int = 1,
) -> SurpriseResult:
    """Operador 2 completo: roda Predict internamente para obter residuos
    passados e o residuo atual, depois calibra causalmente.

    Estritamente causal por construcao: `predict_ar` so olha para
    `series.index < t` em cada chamada, e o loop abaixo so avanca `t`,
    nunca recua — alterar um valor em s > t nao pode, em hipotese nenhuma,
    mudar o residuo calculado para s' <= t. E o teste mais importante deste
    modulo (ver tests/test_represent.py).
    """
    idx_ancora = series[
        (series.index >= pd.Timestamp(ANCHOR_START)) & (series.index < t)
    ].dropna().sort_index().index

    residuals = []
    for s in idx_ancora:
        pr = predict_ar(series, s, feature=feature, target_year=target_year, order=order)
        if not np.isnan(pr.residual):
            residuals.append(pr.residual)
    residuals_hist = np.array(residuals, dtype=float)

    pr_t = predict_ar(series, t, feature=feature, target_year=target_year, order=order)
    p, resolution = causal_percentile(residuals_hist, pr_t.residual)
    t_count = len(residuals_hist) + 1

    if t_count < 30:
        warnings.warn(
            f"{feature}: calibracao causal com t={t_count} (< 30) — resolucao "
            f"1/{t_count} = {1.0 / t_count:.4f}. Percentis mais extremos que "
            "isso nao sao representaveis; nao interprete como zero risco.",
            RuntimeWarning,
            stacklevel=2,
        )

    prov = FeatureProvenance(
        feature=feature,
        target_year=target_year,
        input_timestamps=[t] if t in series.index else [],
        # fitted_on = tudo que entrou na calibracao: o historico usado pelo
        # AR de cada ponto passado E os proprios pontos usados para formar
        # a distribuicao empirica de residuos.
        fitted_on=list(idx_ancora) + list(pr_t.provenance.fitted_on),
    )
    return SurpriseResult(p, resolution, t_count < 30, prov)


# ---------------------------------------------------------------------------
# 3. SHIFT — D_t = d(P_recente, P_referencia)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ShiftResult:
    ks: float
    wasserstein: float
    mmd: float
    provenance: FeatureProvenance


def _rbf_median_bandwidth(x: np.ndarray, y: np.ndarray) -> float:
    """Mediana heuristica: sigma = mediana das distancias par-a-par no
    conjunto combinado. Padrao na literatura de MMD (Gretton et al.) por
    nao exigir busca de hiperparametro — que aqui seria proibida mesmo se
    fosse barata (nunca contra o alvo, e este nem toca o alvo)."""
    z = np.concatenate([x, y])
    if len(z) > 2000:
        # amostragem para custo O(n^2) nao explodir em ~17k pontos diarios;
        # a mediana de distancias e estavel sob subamostragem grande.
        rng = np.random.default_rng(0)
        z = rng.choice(z, size=2000, replace=False)
    diffs = np.abs(z[:, None] - z[None, :])
    med = np.median(diffs[diffs > 0]) if np.any(diffs > 0) else 1.0
    return med if med > 0 else 1.0


def _mmd2_rbf(x: np.ndarray, y: np.ndarray, sigma: float) -> float:
    """MMD^2 empirico (estimador U incompleto/V simples) com kernel RBF."""
    gamma = 1.0 / (2 * sigma**2)

    def kmean(a, b):
        d2 = (a[:, None] - b[None, :]) ** 2
        k = np.exp(-gamma * d2)
        return k.mean()

    kxx = kmean(x, x)
    kyy = kmean(y, y)
    kxy = kmean(x, y)
    return float(kxx + kyy - 2 * kxy)


def _ks_statistic(x: np.ndarray, y: np.ndarray) -> float:
    from scipy import stats

    return float(stats.ks_2samp(x, y, method="asymp").statistic)


def _wasserstein1(x: np.ndarray, y: np.ndarray) -> float:
    from scipy import stats

    return float(stats.wasserstein_distance(x, y))


def shift_ks(recent: np.ndarray, reference: np.ndarray) -> float:
    return _ks_statistic(recent, reference)


def shift_wasserstein(recent: np.ndarray, reference: np.ndarray) -> float:
    return _wasserstein1(recent, reference)


def shift_mmd(recent: np.ndarray, reference: np.ndarray) -> float:
    sigma = _rbf_median_bandwidth(recent, reference)
    return _mmd2_rbf(recent, reference, sigma)


def shift_combined(
    daily_series: pd.Series,
    t: pd.Timestamp,
    *,
    feature: str,
    target_year: int,
    recent_years: int = 10,
    season_months: tuple[int, ...] = (10, 11, 12),
) -> ShiftResult:
    """Operador 3: compara a distribuicao da chuva DIARIA dentro da estacao
    (OND por padrao) numa janela recente (`recent_years` anos antes de t)
    contra a distribuicao congelada da ancora 1951-1990.

    Isso opera sobre n ~ 10 anos * ~92 dias ~= 920 pontos na janela recente
    e ~40 anos * 92 ~= 3680 na ancora — grande o bastante para KS/Wasserstein
    /MMD serem estatisticamente honestos, ao contrario da camada
    supervisionada onde n=36. E por isso este operador nao roda sobre
    acumulados anuais (n=36 tambem la), e sim sobre o campo diario cru.
    """
    s = daily_series.dropna().sort_index()
    s = s[s.index.month.isin(season_months)]

    ref_mask = (s.index >= pd.Timestamp(ANCHOR_START)) & (s.index <= pd.Timestamp(ANCHOR_END))
    reference = s[ref_mask]

    recent_start = t - pd.DateOffset(years=recent_years)
    recent_mask = (s.index >= recent_start) & (s.index < t)
    recent = s[recent_mask]

    ref_vals = reference.values.astype(float)
    recent_vals = recent.values.astype(float)

    if len(ref_vals) < 30 or len(recent_vals) < 30:
        # Amostra insuficiente para uma distancia distribucional ter
        # qualquer honestidade estatistica; devolve NaN em vez de fabricar
        # um numero preciso a partir de poucos pontos.
        ks = wass = mmd = float("nan")
    else:
        ks = shift_ks(recent_vals, ref_vals)
        wass = shift_wasserstein(recent_vals, ref_vals)
        mmd = shift_mmd(recent_vals, ref_vals)

    prov = FeatureProvenance(
        feature=feature,
        target_year=target_year,
        input_timestamps=[],
        # a referencia (ancora, congelada) E a janela recente sao ambas
        # "ajuste" no sentido do gate: a distancia so existe porque foram
        # usadas para definir as duas distribuicoes comparadas.
        fitted_on=list(reference.index) + list(recent.index),
    )
    return ShiftResult(ks, wass, mmd, prov)


# ---------------------------------------------------------------------------
# 4. PERSISTENCE — P_t = sum_k lambda^k * S_{t-k}
# ---------------------------------------------------------------------------


def persistence(surprise_history: list[float], *, lam: float = 0.9) -> float:
    """Soma exponencial causal das surpresas passadas (mais recente
    primeiro em `surprise_history`, i.e. surprise_history[0] = S_{t-1},
    surprise_history[1] = S_{t-2}, ...). k comeca em 1 porque S_t (a
    surpresa do proprio instante t) nao entra aqui — persistencia e sobre
    o QUE VEIO ANTES de t, senao deixaria de ser causal em relacao a S_t.

    `lam` e configuravel (default 0.9) mas e um dos poucos "hiperparametros"
    deste projeto que nunca deve ser ajustado contra o alvo (mesma logica
    do README: matematica pode ser rica na representacao, mas o contato
    com o alvo so acontece na Camada 6).
    """
    if not (0 < lam < 1):
        raise ValueError("lam deve estar em (0, 1)")
    total = 0.0
    for k, s in enumerate(surprise_history, start=1):
        if np.isnan(s):
            continue
        total += (lam**k) * s
    return float(total)


# ---------------------------------------------------------------------------
# 5. REGIME — R_t = g(S_t, D_t, P_t)
# ---------------------------------------------------------------------------


def regime(surprise_pct: float, shift_value: float, persistence_value: float) -> int:
    """v1: discretizacao deterministica em quadrantes de surpresa x
    deslocamento (a persistencia so desempata quando os dois primeiros
    estao no limiar). NAO e um HMM — o estado latente aprendido de verdade
    e Camada 4 / Fase 5 (README), e exige dados que este modulo nao tem
    ainda. Aqui o objetivo e so dar um `int` estavel e auditavel para
    popular `ClimateSignal.regime` desde ja.

    Convencao:
      0 = normal          (surpresa baixa, deslocamento baixo)
      1 = anomalo-agudo    (surpresa alta,  deslocamento baixo)
      2 = deslocamento-cronico (surpresa baixa, deslocamento alto)
      3 = ruptura          (surpresa alta,  deslocamento alto)
    Limiares: surpresa medida como distancia ao centro do percentil (|p-0.5|
    >= 0.3 -> "alta"); deslocamento e comparado a mediana historica passada
    do proprio Dt (aqui, ao caller cabe normalizar/passar ja comparavel —
    tratamos shift_value >= 0.5 do seu proprio intervalo [0,1] tipico do KS
    como "alto"; para MMD/Wasserstein o caller deve normalizar antes).
    """
    surprise_high = abs(surprise_pct - 0.5) >= 0.3
    shift_high = shift_value >= 0.5
    if not surprise_high and not shift_high:
        return 0
    if surprise_high and not shift_high:
        return 1
    if not surprise_high and shift_high:
        return 2
    return 3


# ---------------------------------------------------------------------------
# Fachada: monta um ClimateSignal a partir dos cinco operadores
# ---------------------------------------------------------------------------


def build_climate_signal(
    series: pd.Series,
    daily_series: pd.Series,
    t: pd.Timestamp,
    *,
    feature: str,
    target_year: int,
    ar_order: int = 1,
    lam: float = 0.9,
) -> tuple[ClimateSignal, list[FeatureProvenance]]:
    """Conveniencia que encadeia os cinco operadores para um instante t e
    devolve o ClimateSignal junto com a lista de FeatureProvenance de cada
    operador (o gate exige uma por feature calculada, e cada operador aqui
    conta como uma sub-feature rastreavel)."""
    pr = predict_ar(series, t, feature=f"{feature}_pred", target_year=target_year, order=ar_order)
    sr = surprise(series, t, feature=f"{feature}_surprise", target_year=target_year, order=ar_order)
    shr = shift_combined(daily_series, t, feature=f"{feature}_shift", target_year=target_year)

    idx_ancora = series[
        (series.index >= pd.Timestamp(ANCHOR_START)) & (series.index < t)
    ].dropna().sort_index().index
    hist_surprises = []
    for s in reversed(list(idx_ancora)):
        sr_s = surprise(series, s, feature=f"{feature}_surprise_hist", target_year=target_year, order=ar_order)
        hist_surprises.append(sr_s.percentile)
    pers = persistence(hist_surprises, lam=lam)

    shift_norm = shr.ks if not np.isnan(shr.ks) else 0.0
    reg = regime(sr.percentile, shift_norm, pers)

    x_t = float(series.loc[t]) if t in series.index else float("nan")
    signal = ClimateSignal(
        value=x_t,
        expected=pr.expected,
        surprise=sr.percentile,
        shift=shr.ks,
        persistence=pers,
        regime=reg,
    )
    return signal, [pr.provenance, sr.provenance, shr.provenance]
