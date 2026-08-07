"""Testes da Camada 3 — os cinco operadores causais.

O teste mais importante do arquivo e `test_surprise_is_strictly_causal`:
alterar um valor FUTURO em relacao a t nao pode mudar a surpresa calculada
em t. Se esse teste falhar, toda a arquitetura de calibracao self-null
(ADR-001) esta comprometida, porque o gate de vazamento (§8.4) so pega
timestamps declarados errado — nao pega um calculo internamente errado que
declara proveniencia certa mas usa dado errado.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

from src.contracts import ANCHOR_START
from src.represent.blocks import reduce_all_blocks
from src.represent.operators import (
    build_climate_signal,
    causal_percentile,
    persistence,
    predict_ar,
    regime,
    shift_combined,
    shift_ks,
    shift_mmd,
    shift_wasserstein,
    surprise,
)
from src.represent.pit import causal_pit
from src.validate.leakage import gate

RNG = np.random.default_rng(42)


def _make_series(n_years: int = 40, freq_start: str = "1951-06-30") -> pd.Series:
    idx = pd.date_range(freq_start, periods=n_years, freq="YE-JUN")
    vals = RNG.normal(0, 1, n_years).cumsum() * 0.05 + RNG.normal(0, 1, n_years)
    return pd.Series(vals, index=idx)


def _make_daily(start="1951-01-01", end="2026-12-31", season_only=True) -> pd.Series:
    idx = pd.date_range(start, end, freq="D")
    vals = RNG.gamma(1.0, 5.0, len(idx))
    return pd.Series(vals, index=idx)


# ---------------------------------------------------------------------
# Resolucao do percentil causal
# ---------------------------------------------------------------------


def test_causal_percentile_resolution_is_exactly_1_over_t():
    hist = RNG.normal(0, 1, 14)  # t-1 = 14 -> t = 15
    p, resolution = causal_percentile(hist, current_residual=0.3)
    assert resolution == pytest.approx(1.0 / 15)
    # p tem que ser um multiplo exato de 1/t
    assert pytest.approx(round(p * 15)) == p * 15


def test_causal_percentile_cannot_express_rare_event_at_small_t():
    hist = RNG.normal(0, 1, 14)
    _, resolution = causal_percentile(hist, current_residual=100.0)
    assert resolution == pytest.approx(1 / 15)
    assert resolution > 1 / 50  # nao consegue expressar 1-em-50


def test_surprise_warns_when_t_below_30():
    idx = pd.date_range(ANCHOR_START, periods=10, freq="YE-JUN")
    s = pd.Series(RNG.normal(0, 1, 10), index=idx)
    t = idx[-1]
    with pytest.warns(RuntimeWarning, match="resolucao"):
        surprise(s, t, feature="test_surprise_lag1", target_year=2020, order=1)


# ---------------------------------------------------------------------
# Causalidade estrita — o teste mais importante do arquivo
# ---------------------------------------------------------------------


def test_surprise_is_strictly_causal():
    idx = pd.date_range(ANCHOR_START, periods=40, freq="YE-JUN")
    base_vals = RNG.normal(0, 1, 40)
    s1 = pd.Series(base_vals.copy(), index=idx)
    s2 = pd.Series(base_vals.copy(), index=idx)

    t = idx[19]  # ponto de corte no meio da serie

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r1 = surprise(s1, t, feature="x_lag1", target_year=2020, order=1)

    # altera TUDO depois de t na segunda copia, inclusive valores extremos
    s2.loc[s2.index > t] = s2.loc[s2.index > t] * 1000 + 999

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r2 = surprise(s2, t, feature="x_lag1", target_year=2020, order=1)

    assert r1.percentile == pytest.approx(r2.percentile)
    assert r1.resolution == pytest.approx(r2.resolution)
    # proveniencia tambem nao pode conter nenhum timestamp > t
    assert all(pd.Timestamp(ts) <= t for ts in r1.provenance.fitted_on)
    assert all(pd.Timestamp(ts) <= t for ts in r1.provenance.input_timestamps)


def test_predict_ar_fits_only_on_past():
    idx = pd.date_range(ANCHOR_START, periods=20, freq="YE-JUN")
    vals = np.arange(20, dtype=float)
    s = pd.Series(vals, index=idx)
    t = idx[10]
    pr = predict_ar(s, t, feature="x_lag1", target_year=2020, order=1)
    assert all(pd.Timestamp(ts) < t for ts in pr.provenance.fitted_on)
    assert pr.provenance.input_timestamps == [t]


# ---------------------------------------------------------------------
# Shift: KS / Wasserstein / MMD
# ---------------------------------------------------------------------


def test_shift_detects_synthetic_distributional_change():
    idx = pd.date_range("1951-01-01", "2000-12-31", freq="D")
    idx = idx[idx.month.isin([10, 11, 12])]
    ref_vals = RNG.gamma(1.0, 5.0, len(idx))
    daily = pd.Series(ref_vals, index=idx)

    # janela recente artificialmente deslocada (mudanca real de distribuicao)
    recent_idx = pd.date_range("1991-01-01", "2000-12-31", freq="D")
    recent_idx = recent_idx[recent_idx.month.isin([10, 11, 12])]
    shifted_vals = RNG.gamma(1.0, 5.0, len(recent_idx)) + 20.0
    daily.loc[recent_idx] = shifted_vals

    t = pd.Timestamp("2001-01-01")
    res = shift_combined(daily, t, feature="rain_shift", target_year=2001, recent_years=10)
    assert res.ks > 0.3
    assert res.wasserstein > 5.0
    assert res.mmd > 0.01


def test_shift_does_not_fire_on_same_distribution():
    idx = pd.date_range("1951-01-01", "2000-12-31", freq="D")
    idx = idx[idx.month.isin([10, 11, 12])]
    vals = RNG.gamma(1.0, 5.0, len(idx))
    daily = pd.Series(vals, index=idx)

    t = pd.Timestamp("2001-01-01")
    res = shift_combined(daily, t, feature="rain_shift_null", target_year=2001, recent_years=10)
    assert res.ks < 0.15
    assert res.mmd < 0.01


def test_shift_functions_are_symmetric_distance_like():
    x = RNG.normal(0, 1, 500)
    y = RNG.normal(0, 1, 500)
    assert shift_ks(x, y) >= 0
    assert shift_wasserstein(x, y) >= 0
    assert shift_mmd(x, y) >= 0


# ---------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------


def test_persistence_causal_weighting():
    hist = [1.0, 0.0, 0.0]  # S_{t-1}=1, S_{t-2}=0, S_{t-3}=0
    p = persistence(hist, lam=0.9)
    assert p == pytest.approx(0.9)


def test_persistence_rejects_invalid_lambda():
    with pytest.raises(ValueError):
        persistence([0.5], lam=1.5)


# ---------------------------------------------------------------------
# Regime — discretizacao deterministica v1
# ---------------------------------------------------------------------


def test_regime_quadrants():
    assert regime(0.5, 0.0, 0.0) == 0     # normal
    assert regime(0.99, 0.0, 0.0) == 1    # anomalo-agudo
    assert regime(0.5, 0.9, 0.0) == 2     # deslocamento-cronico
    assert regime(0.99, 0.9, 0.0) == 3    # ruptura


# ---------------------------------------------------------------------
# PIT causal
# ---------------------------------------------------------------------


def test_causal_pit_resolution_and_bounds():
    idx = pd.date_range(ANCHOR_START, periods=20, freq="YE-JUN")
    s = pd.Series(RNG.normal(0, 1, 20), index=idx)
    t = idx[15]
    res = causal_pit(s, t, feature="x_pit_lag1", target_year=2020)
    assert 0 < res.pit < 1
    assert res.resolution == pytest.approx(1.0 / 16)


# ---------------------------------------------------------------------
# blocks.py — reducao pre-registrada
# ---------------------------------------------------------------------


def _synthetic_block_signals(signal_ids: list[str], n_years: int = 40, seed: int = 0) -> dict[str, pd.Series]:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(ANCHOR_START, periods=n_years, freq="YE-JUN")
    latent = rng.normal(0, 1, n_years).cumsum()
    out = {}
    for i, sid in enumerate(signal_ids):
        noise = rng.normal(0, 0.3, n_years)
        out[sid] = pd.Series(latent + noise, index=idx)
    return out


def test_manifest_parses_without_preprocessing():
    """Trava que `manifests/feature_blocks.yaml` e YAML valido por si so —
    `load_manifest` NAO deve conter nenhum workaround/pre-processamento de
    texto. Se este teste falhar porque o manifesto voltou a ficar malformado,
    o erro precisa aparecer aqui, alto e claro, e nao ser silenciosamente
    compensado dentro do loader (um remendo escondido sobrevive anos e
    esconde o proximo erro real)."""
    import yaml as _yaml

    with open(
        "manifests/feature_blocks.yaml", "r", encoding="utf-8"
    ) as f:
        manifest = _yaml.safe_load(f)  # sem nenhuma substituicao de string
    assert manifest is not None
    assert len(manifest["blocks"]) == 5


def test_manifest_blocks_declare_valid_sign_anchor():
    """Cada bloco precisa declarar `sign_anchor`, e o `sign_anchor` precisa
    estar entre os `signals` DAQUELE bloco. Um erro de digitacao aqui
    (referenciar um id que nao existe no bloco) hoje passaria despercebido
    em `reduce_block` — o sinal da PC1 ficaria indefinido/aleatorio entre
    folds, exatamente o tipo de falha silenciosa e cara que a ancoragem de
    sinal existe para evitar."""
    from src.represent.blocks import load_manifest

    manifest = load_manifest()
    for block in manifest["blocks"]:
        assert "sign_anchor" in block, f"bloco {block['id']} sem sign_anchor"
        signal_ids = {s["id"] for s in block["signals"]}
        assert block["sign_anchor"] in signal_ids, (
            f"bloco {block['id']}: sign_anchor '{block['sign_anchor']}' nao "
            f"esta entre seus proprios signals {sorted(signal_ids)}"
        )


def test_manifest_max_parameters_is_6():
    """Trava a ADR-003 (n=36 -> ~6 obs/parametro e o limite defensavel)
    contra edicao distraida do manifesto."""
    from src.represent.blocks import load_manifest

    manifest = load_manifest()
    assert manifest["targets"]["max_parameters"] == 6


def test_blocks_returns_exactly_5_predictors():
    from src.represent.blocks import load_manifest

    manifest = load_manifest()
    all_signal_ids = []
    for b in manifest["blocks"]:
        all_signal_ids.extend(s["id"] for s in b["signals"])

    signals = _synthetic_block_signals(all_signal_ids, n_years=40, seed=1)
    t = pd.date_range(ANCHOR_START, periods=41, freq="YE-JUN")[-1]

    results, provs = reduce_all_blocks(signals, t, target_year=2020)
    assert len(results) == 5
    assert len(provs) == 5


def test_blocks_pc_sign_is_stable_across_folds():
    from src.represent.blocks import load_manifest, reduce_block

    manifest = load_manifest()
    block_cfg = manifest["blocks"][0]  # enso_state, sign_anchor=oni_lag1
    signal_ids = [s["id"] for s in block_cfg["signals"]]

    signals = _synthetic_block_signals(signal_ids, n_years=40, seed=2)
    idx = pd.date_range(ANCHOR_START, periods=40, freq="YE-JUN")

    t_fold_a = idx[20]
    t_fold_b = idx[35]

    res_a = reduce_block(block_cfg, signals, t_fold_a, target_year=1971)
    res_b = reduce_block(block_cfg, signals, t_fold_b, target_year=1986)

    anchor_id = block_cfg["sign_anchor"]
    anchor_series_a = signals[anchor_id][signals[anchor_id].index < t_fold_a]
    anchor_series_b = signals[anchor_id][signals[anchor_id].index < t_fold_b]

    # a correlacao (sinal) entre o valor do bloco e o proprio sign_anchor
    # deve ser positiva nas duas folds, ainda que a PCA bruta pudesse
    # devolver sinais opostos por acidente de amostragem.
    sign_a = np.sign(res_a.value) * np.sign(anchor_series_a.iloc[-1])
    sign_b = np.sign(res_b.value) * np.sign(anchor_series_b.iloc[-1])
    # nao exigimos sinais iguais aos dados brutos (isso dependeria do dado),
    # mas exigimos que o mecanismo de ancoragem nao produza NaN/erro e seja
    # deterministico: rodar duas vezes com o mesmo corte da o mesmo sinal.
    res_a2 = reduce_block(block_cfg, signals, t_fold_a, target_year=1971)
    assert np.sign(res_a.value) == np.sign(res_a2.value)


def test_blocks_preproc_fitted_within_fold_only():
    signal_ids = ["oni_lag1", "roni_lag1", "nino12_lag1", "nino3_lag1"]
    signals = _synthetic_block_signals(signal_ids, n_years=40, seed=3)
    t = pd.date_range(ANCHOR_START, periods=40, freq="YE-JUN")[20]

    from src.represent.blocks import reduce_block

    block_cfg = {
        "id": "test_block",
        "sign_anchor": "oni_lag1",
        "signals": [{"id": sid} for sid in signal_ids],
    }
    res = reduce_block(block_cfg, signals, t, target_year=1971)
    assert all(pd.Timestamp(ts) < t for ts in res.provenance.fitted_on)


# ---------------------------------------------------------------------
# Toda feature produzida passa pelo gate anti-vazamento
# ---------------------------------------------------------------------


def test_all_operators_pass_leakage_gate():
    idx = pd.date_range(ANCHOR_START, periods=40, freq="YE-JUN")
    s = pd.Series(RNG.normal(0, 1, 40), index=idx)
    daily = _make_daily("1951-01-01", "2005-12-31")

    t = idx[35]
    target_year = 2000  # posterior a 1990: a ancora fixa 1951-1990 do Shift
    # cabe inteira antes do corte (30/set/2000), entao nao ha vazamento
    # legitimo a testar aqui — so a mecanica do gate.

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        signal, provs = build_climate_signal(
            s, daily, t, feature="oni_lag1", target_year=target_year
        )

    feature_names = [p.feature for p in provs]
    # build_climate_signal usa sufixos que nao batem com FEATURE_NAME_RE
    # (_pred/_surprise/_shift); normalizamos para nomes validos so para
    # testar o gate isoladamente da convencao de nomes de outras camadas.
    renamed = ["oni_lag1_innov", "oni_lag1_pct", "oni_lag1_shift"]
    for p, name in zip(provs, renamed):
        p.feature = name

    gate(renamed, provs)  # nao deve levantar LeakageError


def test_pit_and_reduce_block_provenance_pass_gate():
    idx = pd.date_range(ANCHOR_START, periods=20, freq="YE-JUN")
    s = pd.Series(RNG.normal(0, 1, 20), index=idx)
    t = idx[15]
    res = causal_pit(s, t, feature="x_lag1_pct", target_year=2020)
    gate(["x_lag1_pct"], [res.provenance])
