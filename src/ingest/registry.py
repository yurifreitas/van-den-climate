"""Registro de ingestores + orquestracao contra manifests/sources.yaml.

Um ingestor concreto se registra com @register("cpc_oni") no import do modulo.
run_all le o catalogo, filtra por status e roda cada ingestor coletando
sucesso/falha independentemente — uma fonte fora do ar (INMET, tipicamente)
nao pode travar as outras 20.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pandas as pd
import yaml

from src.ingest.base import Ingestor, IngestError

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCES_MANIFEST = REPO_ROOT / "manifests" / "sources.yaml"

_REGISTRY: dict[str, Callable[[], Ingestor]] = {}


def register(source_id: str) -> Callable[[type[Ingestor]], type[Ingestor]]:
    """Decorador de classe: @register("cpc_oni") sobre uma subclasse de Ingestor."""

    def deco(cls: type[Ingestor]) -> type[Ingestor]:
        if cls.source_id and cls.source_id != source_id:
            raise ValueError(
                f"registry: {cls.__name__}.source_id={cls.source_id!r} != chave de registro {source_id!r}"
            )
        cls.source_id = source_id
        _REGISTRY[source_id] = cls
        return cls

    return deco


def registered_ids() -> list[str]:
    return sorted(_REGISTRY)


def _load_manifest() -> dict:
    with SOURCES_MANIFEST.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@dataclass
class SourceReport:
    source_id: str
    ok: bool
    rows: int = 0
    period: str = ""
    error: str = ""


@dataclass
class RunReport:
    results: list[SourceReport] = field(default_factory=list)

    @property
    def ok(self) -> list[SourceReport]:
        return [r for r in self.results if r.ok]

    @property
    def failed(self) -> list[SourceReport]:
        return [r for r in self.results if not r.ok]

    def as_text(self) -> str:
        lines = []
        for r in self.results:
            if r.ok:
                lines.append(f"[OK]   {r.source_id:<14} {r.rows:>6} linhas  periodo={r.period}")
            else:
                lines.append(f"[FAIL] {r.source_id:<14} {r.error}")
        lines.append(f"-- {len(self.ok)}/{len(self.results)} fontes ok")
        return "\n".join(lines)


def run_all(ids: list[str] | None = None, only_status: tuple[str, ...] = ("core",)) -> RunReport:
    """Roda os ingestores registrados que constam do manifesto (filtrado por status).

    ids=None -> todas as fontes registradas cujo status em sources.yaml esteja
    em only_status. Passe ids explicito para ignorar o filtro de status.
    """
    manifest = _load_manifest()
    catalog = manifest.get("sources", {})

    if ids is None:
        target_ids = [
            sid for sid in registered_ids()
            if catalog.get(sid, {}).get("status") in only_status
        ]
    else:
        target_ids = list(ids)

    report = RunReport()
    for sid in target_ids:
        cls = _REGISTRY.get(sid)
        if cls is None:
            report.results.append(SourceReport(sid, ok=False, error="nao ha ingestor registrado para esta fonte"))
            continue
        try:
            ingestor = cls()
            df = ingestor.run()
            period = ""
            if not df.empty:
                period = f"{df['timestamp'].min().date()}..{df['timestamp'].max().date()}"
            report.results.append(SourceReport(sid, ok=True, rows=len(df), period=period))
        except IngestError as exc:
            report.results.append(SourceReport(sid, ok=False, error=str(exc)))
        except Exception as exc:  # nunca deixa uma fonte quebrar o run_all inteiro
            report.results.append(SourceReport(sid, ok=False, error=f"{sid}: erro inesperado: {exc}"))

    return report
