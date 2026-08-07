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
    CoverageCell,
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
    """Cobertura sinal x ano, calculada do que JA foi ingerido.

    A versao anterior devolvia lista vazia esperando a Camada 2 (estacoes do
    INMET). Mas a pergunta da tela — "o dado aguenta a pergunta?" — ja tem
    resposta para os quatro indices ingeridos, e essa resposta importa: e ela
    que mostra que o SAM so comeca em 1979 e que o ONI cobre desde 1950.
    Esconder isso ate a Camada 2 existir deixava a tela vazia sem motivo.
    """
    import pandas as pd

    cells: list[CoverageCell] = []
    sources: list[str] = []
    # Frequencia esperada por ano, para virar fracao de cobertura.
    expected = {"cpc_oni": 12, "cpc_soi": 12, "cpc_aao": 12, "psl_nino": 12}

    for source_id, per_year in expected.items():
        path = deps.INTERIM / f"{source_id}.parquet"
        if not path.exists():
            continue
        sources.append(source_id)
        df = pd.read_parquet(path, columns=["signal_id", "timestamp", "value"])
        df = df.dropna(subset=["value"])
        df["year"] = pd.to_datetime(df["timestamp"]).dt.year
        for (signal_id, year), grp in df.groupby(["signal_id", "year"]):
            cells.append(
                CoverageCell(
                    station_id=str(signal_id),
                    year=int(year),
                    coverage_frac=round(min(len(grp) / per_year, 1.0), 3),
                )
            )

    return CoverageResponse(
        cells=sorted(cells, key=lambda c: (c.station_id, c.year)),
        provenance=Provenance(
            basis="measured" if cells else "synthetic",
            horizon="seasonal", source_ids=sources,
            as_of=deps.now_iso(), n_effective=len(cells),
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
