"""Harness de walk-forward (Camada 6, ADR-009).

Este modulo existe ANTES de qualquer modelo. Um modelo e apenas um callable
com a assinatura `Forecaster`; o harness nao sabe nem se importa com o que
ha dentro. E isso que impede afrouxar o criterio quando o resultado desagradar.

Executavel hoje contra a climatologia sozinha — e deve ser, como teste de
sanidade: climatologia contra si mesma tem RPSS = 0 exato.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

import numpy as np

from src.contracts import ANCHOR_END, EVAL_START
from src.validate.leakage import FeatureProvenance, cutoff_for, gate
from src.validate.scoring import Interval, accept, block_bootstrap_ci, permutation_null

ANCHOR_LAST_YEAR = ANCHOR_END.year   # 1990
EVAL_FIRST_YEAR = EVAL_START.year    # 1991
EVAL_LAST_YEAR = 2026
N_EVAL = EVAL_LAST_YEAR - EVAL_FIRST_YEAR + 1  # 36


class Forecaster(Protocol):
    def fit(self, years: list[int]) -> None: ...
    def predict(self, year: int) -> np.ndarray: ...  # (k,) probabilidades de tercil
    def provenance(self, year: int) -> list[FeatureProvenance]: ...
    @property
    def feature_names(self) -> list[str]: ...


@dataclass
class WalkForwardResult:
    years: np.ndarray
    forecast: np.ndarray      # (n, k)
    observed: np.ndarray      # (n, k) one-hot
    climatology: np.ndarray   # (n, k)
    rpss_ci: Interval
    perm_p: float
    accepted: bool

    def report(self) -> str:
        verdict = "ACEITO" if self.accepted else "REJEITADO (mantem climatologia)"
        return (
            f"walk-forward {self.years[0]}-{self.years[-1]}  n={len(self.years)}\n"
            f"RPSS = {self.rpss_ci}\n"
            f"null de permutacao: p = {self.perm_p:.3f}\n"
            f"ADR-007 (limite inferior do IC 90% > 0): {verdict}"
        )


def run(
    model: Forecaster,
    observed_onehot: Callable[[int], np.ndarray],
    climatology: Callable[[int], np.ndarray],
    *,
    first_year: int = EVAL_FIRST_YEAR,
    last_year: int = EVAL_LAST_YEAR,
) -> WalkForwardResult:
    """Um fold por ano-alvo. Treino = ancora + todos os anos anteriores.

    O gate anti-vazamento roda DENTRO do loop, por fold — nao ao final. Um
    vazamento detectado no fold 3 deve interromper antes de contaminar 33
    folds de resultado que pareceriam bons.
    """
    years, fcs, obs, clims = [], [], [], []

    for year in range(first_year, last_year + 1):
        train_years = list(range(1951, year))  # ancora + expanding, exclui o alvo
        model.fit(train_years)

        provs = model.provenance(year)
        gate(model.feature_names, provs)
        assert all(
            (m := p.max_input()) is None or m <= cutoff_for(year) for p in provs
        ), f"fold {year}: proveniencia inconsistente com o corte"

        years.append(year)
        fcs.append(model.predict(year))
        obs.append(observed_onehot(year))
        clims.append(climatology(year))

    F, O, C = np.vstack(fcs), np.vstack(obs), np.vstack(clims)
    ci = block_bootstrap_ci(F, O, C, block_years=3)
    p, _ = permutation_null(F, O, C)
    return WalkForwardResult(np.array(years), F, O, C, ci, p, accept(ci))


class ClimatologyBaseline:
    """Baseline obrigatoria. RPSS contra si mesma = 0 exato — o teste de sanidade
    do harness. Se der diferente de zero, o harness esta errado, nao o modelo."""

    feature_names: list[str] = []

    def __init__(self, k: int = 3) -> None:
        self.k = k

    def fit(self, years: list[int]) -> None:
        pass

    def predict(self, year: int) -> np.ndarray:
        return np.full(self.k, 1.0 / self.k)

    def provenance(self, year: int) -> list[FeatureProvenance]:
        return []
