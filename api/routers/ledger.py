"""§4 do contrato — Ledger: /ledger, /ledger/skill.

O ledger real (ledger/forecasts.parquet) e append-only e so existe depois
que a Camada 6 rodar walk-forward. Ate la, servimos um ledger sintetico
plausivel (mesmo shape do app/fixtures.forecast_ledger) com basis=synthetic
— nunca 500, nunca lista vazia sem explicacao (regra §5.3).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from fastapi import APIRouter

from api import deps
from api.models import (
    LedgerEntry,
    LedgerResponse,
    LedgerSkillResponse,
    Provenance,
    SkillMetric,
)

router = APIRouter(tags=["ledger"])

TARGET_IDS = ["wetday_freq", "wetday_intensity", "p95_daily"]
TARGET_LABELS = {
    "wetday_freq": "Frequencia de dias umidos",
    "wetday_intensity": "Intensidade em dia umido",
    "p95_daily": "P95 diario",
}


def _synthetic_ledger() -> pd.DataFrame:
    """Mesmo gerador de app/fixtures.forecast_ledger, reimplementado aqui
    para nao acoplar api/ a app/ (fronteira de diretorio, ARCHITECTURE §5).
    """
    rng = np.random.default_rng(20260807 + 99)
    years = np.arange(1991, 2026)
    rows = []
    for y in years:
        issued = f"{y}-09-30"
        for tid in TARGET_IDS:
            probs = rng.dirichlet(alpha=[7, 7, 7])
            observed_tercile = int(rng.choice([0, 1, 2], p=[0.33, 0.34, 0.33]))
            rows.append({
                "season": f"OND{y}", "target_id": tid, "target_label": TARGET_LABELS[tid],
                "issued_at": issued,
                "p_below": round(float(probs[0]), 3), "p_near": round(float(probs[1]), 3),
                "p_above": round(float(probs[2]), 3),
                "predicted_tercile": int(np.argmax(probs)),
                "observed_tercile": observed_tercile,
                "climatology_is_forecast": True,
            })
    return pd.DataFrame(rows)


@router.get("/ledger", response_model=LedgerResponse)
def get_ledger(
    target: str | None = None,
    from_: str | None = None,
    to: str | None = None,
) -> LedgerResponse:
    is_synth = not deps.LEDGER_PATH.exists()
    if is_synth:
        df = _synthetic_ledger()
        source_ids: list[str] = []
    else:
        import duckdb
        con = duckdb.connect()
        try:
            df = con.execute(
                "SELECT * FROM read_parquet(?)", [str(deps.LEDGER_PATH)]
            ).fetch_df()
            source_ids = ["ledger.forecasts"]
        except Exception:
            df = _synthetic_ledger()
            is_synth = True
            source_ids = []
        finally:
            con.close()

    if target:
        df = df[df["target_id"] == target]
    if from_:
        df = df[df["season"] >= from_]
    if to:
        df = df[df["season"] <= to]

    entries = [LedgerEntry(**row) for row in df.to_dict(orient="records")]
    return LedgerResponse(
        entries=entries,
        provenance=Provenance(
            basis="synthetic" if is_synth else "measured",
            horizon="seasonal", source_ids=source_ids,
            as_of=deps.now_iso(), n_effective=len(entries),
        ),
    )


@router.get("/ledger/skill", response_model=LedgerSkillResponse)
def get_ledger_skill() -> LedgerSkillResponse:
    # ADR-007: nenhum modelo passou o gate ainda -> RPSS/BSS/CRPS nulos com
    # IC largo (SE(RPSS) ~0.10-0.15 citado em app/fixtures.py), permutation
    # null tambem nao calculado. Isso E o resultado, nao um erro (mesma logica
    # de /forecast/{season} status not_accepted).
    metrics = [
        SkillMetric(metric="RPSS", point=None, lo=None, hi=None, permutation_null=None),
        SkillMetric(metric="BSS", point=None, lo=None, hi=None, permutation_null=None),
        SkillMetric(metric="CRPSS", point=None, lo=None, hi=None, permutation_null=None),
    ]
    return LedgerSkillResponse(
        metrics=metrics,
        provenance=Provenance(
            basis="synthetic", horizon="seasonal", source_ids=[],
            as_of=deps.now_iso(), n_effective=0,
        ),
    )
