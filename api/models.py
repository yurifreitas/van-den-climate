"""Modelos Pydantic v2 de TODAS as respostas do contrato (docs/API_CONTRACT.md).

Por que um modulo so, sem espalhar por router: o objeto `provenance` (§0 do
contrato) e obrigatorio em toda resposta com numero derivado, e a unica forma
de garantir isso e ter UM tipo `Provenance` reutilizado em todo lugar, nunca
reinventado por endpoint. Se cada router declarasse seu proprio provenance
ad-hoc, um campo esquecido nao apareceria no teste ate produzir um numero
"sem selo" — exatamente o bug de interface que o contrato proibe (§0).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Basis = Literal["measured", "modeled", "synthetic"]
Horizon = Literal["seasonal", "subseasonal", "synoptic"]


class Provenance(BaseModel):
    """Proveniencia epistemica — a fronteira medido/prior tornada maquina-legivel.

    `basis` pode ser None apenas no caso explicito do perigo sinotico
    (flash_flood, §3): "fora de escopo" precisa ser um valor declarado, nao
    a ausencia do campo.
    """

    basis: Basis | None = None
    horizon: Horizon
    source_ids: list[str] = Field(default_factory=list)
    as_of: str
    n_effective: int | None = None


# ---------------------------------------------------------------------------
# §1 Estado
# ---------------------------------------------------------------------------

class Headline(BaseModel):
    oni: float | None = None
    classification: str | None = None
    rate_per_season: float | None = None


class StateBlock(BaseModel):
    id: str
    label: str
    percentile: float
    value: float
    trail_12m: list[float]
    provenance: Provenance
    # Regra do contrato §1: t<30 -> resolucao grosseira demais para fingir
    # precisao. Ausente (None) quando nao se aplica, nunca False forcado —
    # False sugeriria que a checagem rodou e passou, quando na verdade o
    # bloco pode nem ter percentil causal (ex.: blocos derivados de outro jeito).
    resolution_warning: bool | None = None


class StateResponse(BaseModel):
    as_of: str
    headline: Headline
    blocks: list[StateBlock]


class RulerChannel(BaseModel):
    signal_id: str
    label: str
    percentile: float
    trail_12m: list[float]
    value_current: float
    resolution_warning: bool | None = None
    provenance: Provenance


class RulerResponse(BaseModel):
    as_of: str
    channels: list[RulerChannel]


class SeriesPoint(BaseModel):
    timestamp: str
    value: float | None
    quality_flag: int | None = None


class SeriesResponse(BaseModel):
    signal: str
    provenance: Provenance
    points: list[SeriesPoint]


# ---------------------------------------------------------------------------
# §2 Previsao
# ---------------------------------------------------------------------------

class TercileSet(BaseModel):
    below: float
    normal: float
    above: float


class ForecastTarget(BaseModel):
    id: str
    label: str
    terciles: TercileSet
    climatology: TercileSet
    provenance: Provenance


class RpssBand(BaseModel):
    point: float | None
    lo: float | None
    hi: float | None


class Acceptance(BaseModel):
    criterion: str
    rpss: RpssBand
    verdict: str


class ForecastResponse(BaseModel):
    season: str
    issued_at: str | None
    status: Literal["accepted", "not_accepted"]
    acceptance: Acceptance
    targets: list[ForecastTarget]


class AttributionShare(BaseModel):
    block_id: str
    label: str
    share_full: float
    share_without_enso: float


class AttributionResponse(BaseModel):
    season: str
    shares: list[AttributionShare]
    provenance: Provenance


class AnalogYear(BaseModel):
    year: int
    similarity: float
    observed_tercile: dict[str, int] | None = None


class AnalogsResponse(BaseModel):
    season: str
    analogs: list[AnalogYear]
    provenance: Provenance


# ---------------------------------------------------------------------------
# §3 Risco
# ---------------------------------------------------------------------------

class Hazard(BaseModel):
    id: str
    label: str
    level: Literal["low", "elevated", "high"] | None
    horizon: Horizon
    basis: Basis | None
    drivers: list[str] = Field(default_factory=list)
    limits: str


class RiskCurrentResponse(BaseModel):
    as_of: str
    hazards: list[Hazard]


class HazardsCatalogResponse(BaseModel):
    hazards: list[Hazard]


# ---------------------------------------------------------------------------
# §4 Ledger e saude
# ---------------------------------------------------------------------------

class LedgerEntry(BaseModel):
    season: str
    target_id: str
    target_label: str
    issued_at: str
    p_below: float
    p_near: float
    p_above: float
    predicted_tercile: int
    observed_tercile: int | None
    climatology_is_forecast: bool


class LedgerResponse(BaseModel):
    entries: list[LedgerEntry]
    provenance: Provenance


class SkillMetric(BaseModel):
    metric: str
    point: float | None
    lo: float | None
    hi: float | None
    permutation_null: float | None = None


class LedgerSkillResponse(BaseModel):
    metrics: list[SkillMetric]
    provenance: Provenance


class CoverageCell(BaseModel):
    station_id: str
    year: int
    coverage_frac: float


class CoverageResponse(BaseModel):
    cells: list[CoverageCell]
    provenance: Provenance


class BreakPoint(BaseModel):
    station_id: str
    date: str
    kind: str
    confidence: float | None = None


class BreaksResponse(BaseModel):
    breaks: list[BreakPoint]
    provenance: Provenance


class SourceStatus(BaseModel):
    source_id: str
    last_ingested_at: str | None
    sha256: str | None
    status: Literal["ok", "stale", "missing"]
    rows: int | None = None
    notes: str | None = None


class SourcesHealthResponse(BaseModel):
    sources: list[SourceStatus]


class MetaResponse(BaseModel):
    contract_version: str
    api_prefix: str
    generated_at: str
