"""Testes do harness — rodam sem nenhum dado ingerido.

O primeiro teste e o mais importante do repositorio: climatologia contra si
mesma tem que dar RPSS = 0 exato. Se falhar, tudo o que vier depois e ruido.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.contracts import ContractError, validate_feature_name
from src.validate.leakage import FeatureProvenance, LeakageError, cutoff_for, gate
from src.validate.scoring import Interval, accept, block_bootstrap_ci, rpss
from src.validate.walkforward import ClimatologyBaseline, N_EVAL, run

K = 3
RNG = np.random.default_rng(0)


def _onehot(year: int) -> np.ndarray:
    return np.eye(K)[(year * 7) % K]


def _clim(year: int) -> np.ndarray:
    return np.full(K, 1.0 / K)


def test_climatology_scores_exactly_zero():
    F = np.full((N_EVAL, K), 1.0 / K)
    O = np.vstack([_onehot(y) for y in range(1991, 2027)])
    assert rpss(F, O, F) == pytest.approx(0.0, abs=1e-12)


def test_walkforward_runs_and_rejects_climatology():
    res = run(ClimatologyBaseline(K), _onehot, _clim)
    assert len(res.years) == N_EVAL == 36
    assert res.rpss_ci.point == pytest.approx(0.0, abs=1e-12)
    assert not res.accepted, "climatologia nao pode ser aceita contra si mesma"


def test_perfect_forecast_is_accepted():
    O = np.vstack([_onehot(y) for y in range(1991, 2027)])
    F = 0.98 * O + 0.01
    C = np.full_like(O, 1.0 / K)
    ci = block_bootstrap_ci(F, O, C, n_boot=500)
    assert accept(ci) and ci.lo > 0.5


def test_acceptance_uses_lower_bound_not_point():
    # RPSS pontual positivo com IC cruzando zero NAO passa (ADR-007)
    assert not accept(Interval(point=0.18, lo=-0.04, hi=0.39))
    assert accept(Interval(point=0.18, lo=0.02, hi=0.39))


def test_feature_names_must_declare_lag():
    validate_feature_name("oni_lag3_son")
    validate_feature_name("satl_shift")
    with pytest.raises(ContractError):
        validate_feature_name("oni")


def test_leakage_gate_catches_future_input():
    p = FeatureProvenance("oni_lag1", 2020, input_timestamps=[pd.Timestamp("2020-11-15")])
    with pytest.raises(LeakageError, match="VAZAMENTO"):
        gate(["oni_lag1"], [p])


def test_leakage_gate_catches_preproc_fitted_on_future():
    # O modo de falha real: o valor respeita o corte, mas o z-score/PCA nao.
    p = FeatureProvenance(
        "oni_lag1",
        2020,
        input_timestamps=[pd.Timestamp("2020-08-01")],
        fitted_on=[pd.Timestamp("2024-01-01")],
    )
    with pytest.raises(LeakageError, match="fit"):
        gate(["oni_lag1"], [p])


def test_leakage_gate_requires_declared_provenance():
    with pytest.raises(LeakageError, match="sem proveniencia"):
        gate(["sam_lag1"], [])


def test_cutoff_is_september_30():
    assert cutoff_for(2026) == pd.Timestamp("2026-09-30")
