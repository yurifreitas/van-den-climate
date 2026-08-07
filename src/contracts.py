"""Contratos de dados (§8.3).

Toda serie que entra na engine passa por aqui. O esquema unico e o que
permite que os cinco operadores da Camada 3 tenham interface unica.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from enum import IntEnum

import pandas as pd

SCHEMA_VERSION = 1


class QualityFlag(IntEnum):
    OK = 0
    INTERPOLATED = 1
    SUSPECT = 2
    INVALID = 3


class AnchorMode(str):
    FIXED = "fixed_1951_1990"
    RELATIVE = "relative_30y"


ANCHOR_START = dt.date(1951, 1, 1)
ANCHOR_END = dt.date(1990, 12, 31)
EVAL_START = dt.date(1991, 1, 1)

SERIES_COLUMNS = {
    "signal_id": "string",
    "timestamp": "datetime64[ns]",
    "value": "float64",
    "source_version": "string",
    "quality_flag": "int8",
    "anchor_mode": "string",
}

# Nome de feature DEVE carregar a defasagem — torna vazamento visivel por
# inspecao (§8.3). `oni_lag3_son`, nunca `oni`.
FEATURE_NAME_RE = re.compile(
    r"^[a-z0-9]+(_[a-z0-9]+)*_(lag\d+|innov|trend|shift|pct|pc\d+)(_[a-z]{3})?$"
)


class ContractError(ValueError):
    pass


def validate_series(df: pd.DataFrame, *, name: str = "<series>") -> pd.DataFrame:
    """Valida e normaliza uma serie contra o esquema unico."""
    missing = set(SERIES_COLUMNS) - set(df.columns)
    if missing:
        raise ContractError(f"{name}: colunas ausentes {sorted(missing)}")

    out = df.loc[:, list(SERIES_COLUMNS)].copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"])

    if out.duplicated(["signal_id", "timestamp"]).any():
        dupes = out[out.duplicated(["signal_id", "timestamp"], keep=False)]
        raise ContractError(f"{name}: {len(dupes)} linhas duplicadas (signal_id, timestamp)")

    bad = set(out["quality_flag"].unique()) - {int(f) for f in QualityFlag}
    if bad:
        raise ContractError(f"{name}: quality_flag invalida {bad}")

    bad_anchor = set(out["anchor_mode"].unique()) - {AnchorMode.FIXED, AnchorMode.RELATIVE}
    if bad_anchor:
        raise ContractError(f"{name}: anchor_mode invalido {bad_anchor}")

    # Valor ausente sem flag e o modo de falha silencioso mais comum:
    # 'ausente' virando zero em precipitacao.
    unflagged_na = out["value"].isna() & (out["quality_flag"] == QualityFlag.OK)
    if unflagged_na.any():
        raise ContractError(
            f"{name}: {int(unflagged_na.sum())} valores nulos com quality_flag=OK"
        )

    return out.sort_values(["signal_id", "timestamp"]).reset_index(drop=True)


def validate_feature_name(name: str) -> None:
    if not FEATURE_NAME_RE.match(name):
        raise ContractError(
            f"nome de feature '{name}' nao declara defasagem/derivacao; "
            "use sufixo _lagN, _innov, _trend, _shift, _pct ou _pcN"
        )


@dataclass(frozen=True)
class ClimateSignal:
    """Saida canonica dos cinco operadores da Camada 3."""

    value: float
    expected: float          # Predict
    surprise: float          # Surprise (percentil causal, resolucao 1/t)
    shift: float             # Shift  (distancia distribucional vs ancora)
    persistence: float       # Persistence (soma exponencial de surpresas)
    regime: int | None = None  # Regime (estado latente, se disponivel)

    @property
    def surprise_resolution(self) -> None:
        raise NotImplementedError("resolucao 1/t vem do operador, nao do container")
