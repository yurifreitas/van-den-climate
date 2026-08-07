"""§4 do contrato — Saude: /health/coverage, /health/breaks, /health/sources.

`/health/sources` e o unico endpoint que le `data/raw/<source_id>/<ts>/
provenance.json` diretamente (via api.deps.sources_health) — e o painel
operacional citado em ARCHITECTURE §1: fonte que falhou vira lacuna
declarada (status="missing"/"stale"), nunca excecao silenciosa.
"""
from __future__ import annotations

from fastapi import APIRouter

from api import deps
from api.models import (
    BreaksResponse,
    CoverageResponse,
    Provenance,
    SourcesHealthResponse,
    SourceStatus,
)

router = APIRouter(tags=["health"])


@router.get("/health/sources", response_model=SourcesHealthResponse)
def get_sources_health() -> SourcesHealthResponse:
    rows = deps.sources_health()
    return SourcesHealthResponse(sources=[SourceStatus(**r) for r in rows])


@router.get("/health/coverage", response_model=CoverageResponse)
def get_coverage() -> CoverageResponse:
    # Cobertura estacao x ano depende do INMET (Camada 2, station_precip),
    # que ainda nao foi ingerido — data/interim/station_precip.parquet nao
    # existe. Devolve vazio + basis=synthetic, nunca 500 (regra §5.3): a
    # ausencia da Camada 2 e uma lacuna declarada, nao uma excecao.
    path = deps.INTERIM / "station_precip.parquet"
    is_synth = not path.exists()
    return CoverageResponse(
        cells=[],
        provenance=Provenance(
            basis="synthetic" if is_synth else "measured",
            horizon="seasonal", source_ids=[] if is_synth else ["station_precip"],
            as_of=deps.now_iso(), n_effective=0,
        ),
    )


@router.get("/health/breaks", response_model=BreaksResponse)
def get_breaks() -> BreaksResponse:
    # Deteccao de quebra de homogeneidade (ARCHITECTURE §3) tambem depende
    # da Camada 2 sobre estacoes, ainda nao ingerida — mesmo raciocinio do
    # /health/coverage acima.
    path = deps.INTERIM / "station_precip.parquet"
    is_synth = not path.exists()
    return BreaksResponse(
        breaks=[],
        provenance=Provenance(
            basis="synthetic" if is_synth else "measured",
            horizon="seasonal", source_ids=[] if is_synth else ["station_precip"],
            as_of=deps.now_iso(), n_effective=0,
        ),
    )
