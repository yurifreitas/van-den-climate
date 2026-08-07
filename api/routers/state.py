"""§1 do contrato — Estado: /state, /state/ruler, /series/{signal}."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api import deps
from api.models import (
    Headline,
    Provenance,
    RulerChannel,
    RulerResponse,
    SeriesPoint,
    SeriesResponse,
    StateBlock,
    StateResponse,
)

router = APIRouter(tags=["state"])

# Canais da Regua de Surpresa — mesmos 5 canais de app/fixtures.surprise_state,
# mapeados para signals que deps.get_series conhece. `oni_innovation_jas` e
# `year_index` sao derivados da propria serie ONI (residuo / indice de tempo),
# igual ao que fixtures.py faz — mantem os dois front-ends (Streamlit e este)
# semanticamente coerentes sem compartilhar codigo entre `app/` e `api/`.
CHANNELS = [
    ("oni", "oni_lag1", "ONI (Estado ENSO)"),
    ("oni", "oni_innovation_jas", "Dinamica ENSO (inovacao)"),
    ("sam", "sam_cpc_son", "SAM"),
    ("soi", "soi_lag1", "SOI"),
]


def _block_from_signal(signal: str, block_id: str, label: str) -> StateBlock | None:
    res = deps.get_series(signal)
    if res is None or res.df.empty:
        return None
    df = res.df.sort_values("timestamp")
    values = df["value"].to_numpy()
    if block_id == "oni_innovation_jas":
        import numpy as np
        values = np.diff(values, prepend=values[0])
    pct = deps.causal_percentile(values)
    n = len(values)
    basis = "synthetic" if res.is_synthetic else "measured"
    return StateBlock(
        id=block_id,
        label=label,
        percentile=round(float(pct[-1]), 4),
        value=round(float(values[-1]), 4),
        trail_12m=[round(float(x), 4) for x in pct[-12:]],
        provenance=Provenance(
            basis=basis, horizon="seasonal",
            source_ids=res.source_ids, as_of=deps.now_iso(), n_effective=n,
        ),
        # Regra do contrato §1: t<30 -> resolucao grosseira, avisar o front.
        resolution_warning=n < 30,
    )


@router.get("/state", response_model=StateResponse)
def get_state() -> StateResponse:
    headline_dict, is_synth, source_ids = deps.state_headline()
    blocks: list[StateBlock] = []
    for signal, block_id, label in CHANNELS:
        blk = _block_from_signal(signal, block_id, label)
        if blk is not None:
            blocks.append(blk)
    return StateResponse(
        as_of=deps.now_iso()[:10],
        headline=Headline(**headline_dict),
        blocks=blocks,
    )


@router.get("/state/ruler", response_model=RulerResponse)
def get_ruler() -> RulerResponse:
    channels: list[RulerChannel] = []
    for signal, block_id, label in CHANNELS:
        blk = _block_from_signal(signal, block_id, label)
        if blk is None:
            continue
        channels.append(RulerChannel(
            signal_id=blk.id,
            label=blk.label,
            percentile=blk.percentile,
            trail_12m=blk.trail_12m,
            value_current=blk.value,
            resolution_warning=blk.resolution_warning,
            provenance=blk.provenance,
        ))
    return RulerResponse(as_of=deps.now_iso()[:10], channels=channels)


@router.get("/series/{signal}", response_model=SeriesResponse)
def get_series(
    signal: str,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
) -> SeriesResponse:
    res = deps.get_series(signal)
    if res is None:
        # signal fora de {oni,sam,soi,nino34,satl}: 404 e resposta correta
        # (nao e "fonte ausente", e rota inexistente — a regra §5.3 de
        # "erro e resposta" vale para fonte de dado, nao para rota invalida).
        raise HTTPException(status_code=404, detail=f"signal desconhecido: {signal}")

    df = res.df.sort_values("timestamp")
    if from_:
        df = df[df["timestamp"] >= from_]
    if to:
        df = df[df["timestamp"] <= to]

    points = [
        SeriesPoint(
            timestamp=ts.strftime("%Y-%m-%d"),
            value=None if val != val else float(val),  # NaN -> None
            quality_flag=int(qf) if "quality_flag" in df.columns and qf == qf else None,
        )
        for ts, val, qf in zip(
            df["timestamp"], df["value"],
            df["quality_flag"] if "quality_flag" in df.columns else [None] * len(df),
        )
    ]
    basis = "synthetic" if res.is_synthetic else "measured"
    return SeriesResponse(
        signal=signal,
        provenance=Provenance(
            basis=basis, horizon="seasonal", source_ids=res.source_ids,
            as_of=deps.now_iso(), n_effective=len(points),
        ),
        points=points,
    )
