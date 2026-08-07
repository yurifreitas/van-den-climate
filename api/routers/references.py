"""Catalogo de referencias — GET /references.

Le e parseia `manifests/references.yaml` (leitura, nunca escrita) e serve o
conteudo estruturado via modelos Pydantic. Nao faz parte do contrato v0
congelado (docs/API_CONTRACT.md §0-4) — e um endpoint auxiliar para a visao
"Referencias" do front, mas segue a mesma filosofia de "erro e resposta":
YAML ausente ou malformado devolve catalogo vazio, nunca 500.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter

from api.models import (
    ReferenceAdversarial,
    ReferencePerson,
    ReferencePrecedent,
    ReferenceSchool,
    ReferencesResponse,
)

router = APIRouter(tags=["references"])

ROOT = Path(__file__).resolve().parents[2]
REFERENCES_PATH = ROOT / "manifests" / "references.yaml"


def _load_raw() -> dict[str, Any]:
    if not REFERENCES_PATH.exists():
        return {}
    try:
        with REFERENCES_PATH.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return data or {}
    except Exception:
        # YAML corrompido nao pode virar 500 na central de risco.
        return {}


def _build_catalog() -> ReferencesResponse:
    raw = _load_raw()

    schools: list[ReferenceSchool] = []
    for s in raw.get("schools", []) or []:
        people = [
            ReferencePerson(
                id=p["id"],
                name=p["name"],
                affiliation=p.get("affiliation"),
                status=p["status"],
                resolve=(p.get("resolve") or "").strip(),
                work=p.get("work"),
            )
            for p in s.get("people", []) or []
        ]
        schools.append(
            ReferenceSchool(
                id=s["id"],
                label=s["label"],
                layer=s.get("layer", ""),
                why=(s.get("why") or "").strip(),
                people=people,
            )
        )

    precedents = [
        ReferencePrecedent(
            ours=p.get("ours", ""),
            established=p.get("established", ""),
            by=p.get("by"),
            note=p.get("note"),
        )
        for p in raw.get("precedents", []) or []
    ]

    adversarial = [
        ReferenceAdversarial(
            claim=a.get("claim", ""),
            challenge=(a.get("challenge") or "").strip(),
            by=a.get("by"),
            consequence=(a.get("consequence") or "").strip(),
        )
        for a in raw.get("adversarial", []) or []
    ]

    return ReferencesResponse(
        version=raw.get("version", 1),
        updated=str(raw.get("updated", "")),
        reading_order=list(raw.get("reading_order", []) or []),
        schools=schools,
        precedents=precedents,
        adversarial=adversarial,
    )


@router.get("/references", response_model=ReferencesResponse)
def get_references() -> ReferencesResponse:
    return _build_catalog()
