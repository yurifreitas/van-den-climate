"""Metricas e criterio de aceitacao (§10, ADR-007).

Regra que governa este modulo: nenhuma metrica e reportada como valor pontual.
Com n=36, SE(RPSS) ~ 0.10-0.15 — o valor pontual sozinho e desinformativo.
Toda funcao publica aqui retorna (estimativa, IC).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

RNG_SEED = 20260807  # datado como o pre-registro; nunca variar para "melhorar" IC


@dataclass(frozen=True)
class Interval:
    point: float
    lo: float
    hi: float
    level: float = 0.90

    def __str__(self) -> str:
        return f"{self.point:+.3f} [{self.lo:+.3f}, {self.hi:+.3f}] ({self.level:.0%})"

    @property
    def excludes_zero_above(self) -> bool:
        """Criterio de aceitacao da ADR-007: limite INFERIOR > 0."""
        return self.lo > 0.0


def rps(forecast: np.ndarray, observed: np.ndarray) -> np.ndarray:
    """Ranked Probability Score por ano. forecast (n, k), observed one-hot (n, k)."""
    cf = np.cumsum(forecast, axis=1)
    co = np.cumsum(observed, axis=1)
    return np.sum((cf - co) ** 2, axis=1)


def rpss(forecast: np.ndarray, observed: np.ndarray, climatology: np.ndarray) -> float:
    """RPSS vs climatologia. Media dos RPS antes da razao (nao razao das medias)."""
    num = rps(forecast, observed).mean()
    den = rps(climatology, observed).mean()
    return float("nan") if den == 0 else 1.0 - num / den


def block_bootstrap_ci(
    forecast: np.ndarray,
    observed: np.ndarray,
    climatology: np.ndarray,
    *,
    block_years: int = 3,
    n_boot: int = 5000,
    level: float = 0.90,
) -> Interval:
    """IC por bootstrap em blocos.

    Blocos de 3 anos preservam a autocorrelacao de baixa frequencia (PDO,
    persistencia de ENSO multianual). Bootstrap i.i.d. estreitaria o IC
    artificialmente — que e exatamente o erro que a ADR-007 existe para evitar.
    """
    n = len(observed)
    point = rpss(forecast, observed, climatology)
    rng = np.random.default_rng(RNG_SEED)
    n_blocks = int(np.ceil(n / block_years))
    starts = np.arange(0, n - block_years + 1)

    draws = np.empty(n_boot)
    for b in range(n_boot):
        idx = np.concatenate(
            [np.arange(s, s + block_years) for s in rng.choice(starts, n_blocks)]
        )[:n]
        draws[b] = rpss(forecast[idx], observed[idx], climatology[idx])

    a = (1.0 - level) / 2.0
    lo, hi = np.nanquantile(draws, [a, 1.0 - a])
    return Interval(point=point, lo=float(lo), hi=float(hi), level=level)


def permutation_null(
    forecast: np.ndarray,
    observed: np.ndarray,
    climatology: np.ndarray,
    *,
    n_perm: int = 5000,
) -> tuple[float, np.ndarray]:
    """p-valor sob a hipotese de que a associacao previsao-observacao e nula.

    Com n=36 a distribuicao nula e larga; e ela, e nao a intuicao, que diz o
    que conta como skill.
    """
    rng = np.random.default_rng(RNG_SEED + 1)
    obs_point = rpss(forecast, observed, climatology)
    null = np.array(
        [rpss(forecast, observed[rng.permutation(len(observed))], climatology)
         for _ in range(n_perm)]
    )
    p = float((1 + np.sum(null >= obs_point)) / (n_perm + 1))
    return p, null


def accept(interval: Interval) -> bool:
    """Criterio unico da ADR-007. Sem variantes, sem 'quase'."""
    return interval.excludes_zero_above
