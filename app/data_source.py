"""Deteccao automatica dado real vs sintetico (§9.1).

Por que isolado num modulo proprio: outro agente esta gerando os parquets
reais em `data/interim` e `data/features` em paralelo. O front nao pode saber
QUANDO isso termina — entao cada visao consulta este modulo a cada reload do
Streamlit e troca de fonte sozinha, sem flag manual, sem redeploy. Enquanto o
parquet esperado nao existir, cai em `app/fixtures.py` e a visao exibe o selo
"DADO SINTETICO". No instante em que o arquivo aparecer em disco, a mesma
chamada passa a ler o parquet real e o selo some — essa e a garantia central
pedida pela tarefa.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

from app import fixtures

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
FEATURES = ROOT / "data" / "features"
LEDGER_PATH = ROOT / "ledger" / "forecasts.parquet"

# Caminhos esperados do dado real, por visao. Mantidos num so lugar para que
# a lista de "o que falta" (visao Saude dos dados / empty states) e a logica
# de deteccao nunca divirjam.
EXPECTED = {
    "oni": INTERIM / "cpc_oni.parquet",
    "sam": INTERIM / "cpc_aao.parquet",
    "satl": FEATURES / "signals" / "satl.parquet",
    "station_precip": INTERIM / "station_precip.parquet",
    "surprise_state": FEATURES / "state.parquet",
    "block_attribution": FEATURES / "attribution.parquet",
    "target_forecast": FEATURES / "forecast_targets.parquet",
    "reliability": FEATURES / "reliability.parquet",
    "quality": FEATURES / "quality.parquet",
    "ledger": LEDGER_PATH,
}


# Qual signal_id extrair de cada parquet de ingestao. Vazio = usar o arquivo
# inteiro (features derivadas ja vem com uma serie so).
SIGNAL_FILTER = {
    "oni": "oni",
    "sam": "sam_cpc_monthly",
}


@dataclass(frozen=True)
class Resolved:
    """Envelope de retorno: dado + proveniencia explicita (real ou sintetico).

    Nenhum painel deve exibir um numero sem que este `is_synthetic` tenha
    sido consultado — e o mecanismo que sustenta o selo "DADO SINTETICO".
    """

    df: pd.DataFrame
    is_synthetic: bool
    source_path: Path | None


def _resolve(key: str, fixture_fn: Callable[[], pd.DataFrame]) -> Resolved:
    path = EXPECTED[key]
    if path.exists():
        try:
            df = pd.read_parquet(path)
            # Um parquet de ingestao pode conter varios signal_id (psl_nino traz
            # 4 caixas Nino no mesmo arquivo). A visao quer UMA serie — filtrar
            # aqui, e nao no grafico, mantem a costura num lugar so.
            sig = SIGNAL_FILTER.get(key)
            if sig and "signal_id" in df.columns:
                df = df[df["signal_id"] == sig]
            if df.empty:
                raise ValueError(f"{path.name} sem linhas para signal_id={sig!r}")
            return Resolved(df, is_synthetic=False, source_path=path)
        except Exception:
            # parquet corrompido/parcial (escrita concorrente do outro agente)
            # nao pode derrubar o front — volta para fixtures ate estabilizar.
            pass
    return Resolved(fixture_fn(), is_synthetic=True, source_path=None)


def resolve_oni() -> Resolved:
    return _resolve("oni", fixtures.oni_monthly)


def resolve_sam() -> Resolved:
    return _resolve("sam", fixtures.sam_monthly)


def resolve_satl() -> Resolved:
    return _resolve("satl", fixtures.satl_monthly)


def resolve_station_precip() -> Resolved:
    return _resolve("station_precip", fixtures.station_daily_precip)


def resolve_surprise_state() -> Resolved:
    return _resolve("surprise_state", fixtures.surprise_state)


def resolve_block_attribution() -> Resolved:
    return _resolve("block_attribution", fixtures.block_attribution)


def resolve_target_forecast() -> Resolved:
    return _resolve("target_forecast", fixtures.target_forecast_vs_climatology)


def resolve_reliability() -> Resolved:
    return _resolve("reliability", fixtures.reliability_data)


def resolve_quality() -> Resolved:
    """Sem fixture dedicada de 'quality' — deriva-se da chuva sintetica por
    estacao (station_daily_precip), que ja carrega quality_flag por dia.
    """
    path = EXPECTED["quality"]
    if path.exists():
        try:
            return Resolved(pd.read_parquet(path), is_synthetic=False, source_path=path)
        except Exception:
            pass
    return Resolved(fixtures.station_daily_precip(), is_synthetic=True, source_path=None)


def resolve_ledger() -> Resolved:
    return _resolve("ledger", fixtures.forecast_ledger)
