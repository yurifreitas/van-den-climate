"""§2 do contrato — Previsao: /forecast/{season}, /attribution, /analogs.

ADR-007/012 e a secao 2 do contrato deixam explicito que nenhum modelo passa
o gate de aceitacao (limite inferior do IC 90% de RPSS > 0) ainda —
`feature_blocks.yaml` foi congelado em 2026-08-07 e a Camada 5 (modelagem)
nao rodou. Por isso TODO season aqui devolve status "not_accepted" com a
climatologia vigente: isso e o resultado correto, nao um placeholder a
substituir. Quando a Camada 6 (walk-forward) produzir um RPSS que passe o
gate, este router passa a ler de `data/features`/ledger — a mudanca fica
isolada aqui, o contrato nao muda.
"""
from __future__ import annotations

from api import deps
from fastapi import APIRouter

from api.models import (
    Acceptance,
    AnalogsResponse,
    AnalogYear,
    AttributionResponse,
    AttributionShare,
    ForecastResponse,
    ForecastTarget,
    Provenance,
    RpssBand,
    TercileSet,
)

router = APIRouter(tags=["forecast"])

TARGETS = [
    ("wetday_freq", "Frequencia de dias umidos"),
    ("wetday_intensity", "Intensidade em dia umido"),
    ("p95_daily", "P95 diario"),
]


@router.get("/forecast/{season}", response_model=ForecastResponse)
def get_forecast(season: str) -> ForecastResponse:
    clim = TercileSet(below=0.33, normal=0.33, above=0.34)
    targets = [
        ForecastTarget(
            id=tid, label=label,
            terciles=clim,  # nenhum modelo aceito -> previsao == climatologia (ADR-007)
            climatology=clim,
            provenance=Provenance(
                basis="measured", horizon="seasonal", source_ids=["climatology_1951_1990"],
                as_of=deps.now_iso(), n_effective=36,
            ),
        )
        for tid, label in TARGETS
    ]
    return ForecastResponse(
        season=season,
        issued_at=None,
        status="not_accepted",
        acceptance=Acceptance(
            criterion="lower bound of 90% CI of RPSS > 0",
            rpss=RpssBand(point=None, lo=None, hi=None),
            verdict="climatology remains in force",
        ),
        targets=targets,
    )


@router.get("/forecast/{season}/attribution", response_model=AttributionResponse)
def get_attribution(season: str) -> AttributionResponse:
    # Sem modelo aceito, nao ha atribuicao real a reportar — devolvemos as
    # shares como 0.0 explicito (nao omitidas) com basis=synthetic, para que
    # o front saiba diferenciar "atribuicao mede zero" de "endpoint quebrado".
    blocks = [
        ("enso_state", "Estado ENSO"), ("enso_dynamics", "Dinamica ENSO"),
        ("sam", "SAM"), ("satl", "Atlantico Sul"), ("trend", "Tendencia"),
    ]
    shares = [
        AttributionShare(block_id=bid, label=label, share_full=0.0, share_without_enso=0.0)
        for bid, label in blocks
    ]
    return AttributionResponse(
        season=season, shares=shares,
        provenance=Provenance(
            basis="synthetic", horizon="seasonal", source_ids=[],
            as_of=deps.now_iso(), n_effective=0,
        ),
    )


@router.get("/forecast/{season}/analogs", response_model=AnalogsResponse)
def get_analogs(season: str) -> AnalogsResponse:
    # Anos analogos por proximidade de ONI (medida real, sem exigir modelo
    # aceito) — util como contexto mesmo com a climatologia vigente.
    res = deps.get_series("oni")
    analogs: list[AnalogYear] = []
    basis = "synthetic"
    source_ids: list[str] = []
    if res is not None and not res.df.empty:
        df = res.df.copy()
        df["year"] = df["timestamp"].dt.year
        target_month = df["timestamp"].dt.month == df["timestamp"].dt.month.iloc[-1]
        current = float(df["value"].iloc[-1])
        yearly = df[target_month].groupby("year")["value"].mean().dropna()
        diffs = (yearly - current).abs().sort_values()
        for year, _ in diffs.head(5).items():
            sim = 1.0 / (1.0 + float(diffs.loc[year]))
            analogs.append(AnalogYear(year=int(year), similarity=round(sim, 3)))
        basis = "synthetic" if res.is_synthetic else "measured"
        source_ids = res.source_ids
    return AnalogsResponse(
        season=season, analogs=analogs,
        provenance=Provenance(
            basis=basis, horizon="seasonal", source_ids=source_ids,
            as_of=deps.now_iso(), n_effective=len(analogs),
        ),
    )
