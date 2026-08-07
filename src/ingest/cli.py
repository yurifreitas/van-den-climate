"""CLI de ingestao.

Uso:
    python -m src.ingest.cli --all
    python -m src.ingest.cli --source cpc_oni --source cpc_soi
    python -m src.ingest.cli --all --offline
"""
from __future__ import annotations

import argparse
import os
import sys

import src.ingest  # registra os ingestores concretos (efeito colateral do import)
from src.ingest.registry import registered_ids, run_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingestao Camada 1 — Engine Climatica RS")
    parser.add_argument("--all", action="store_true", help="roda todas as fontes core registradas")
    parser.add_argument("--source", action="append", default=None, help="id de fonte especifica (repetivel)")
    parser.add_argument("--offline", action="store_true", help="forca CLIMATE_OFFLINE=1 (nunca bate na rede)")
    parser.add_argument(
        "--status", action="append", default=None,
        help="filtra por status do manifesto (core, backup, optional, ...); default: core",
    )
    args = parser.parse_args(argv)

    if args.offline:
        os.environ["CLIMATE_OFFLINE"] = "1"

    if not args.all and not args.source:
        parser.print_help()
        print(f"\nFontes registradas: {', '.join(registered_ids())}")
        return 1

    only_status = tuple(args.status) if args.status else ("core",)
    report = run_all(ids=args.source, only_status=only_status)

    print(report.as_text())
    return 0 if not report.failed else 1


if __name__ == "__main__":
    sys.exit(main())
