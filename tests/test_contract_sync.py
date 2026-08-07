"""Sincronia entre o schema da API e os tipos do front.

Por que este teste existe: sete telas quebraram, todas pela mesma causa. A
API devolvia `shares`/`source_id`/`sha256`/`metric`/`signal_id`; o front lia
`blocks`/`label`/`hash`/`name`/`id`. Nenhum teste de nenhum dos lados podia
pegar — os tipos TypeScript foram escritos a mao a partir do contrato em
Markdown, e Markdown nao compila.

Os sintomas eram piores que uma excecao: tabela vazia sem erro, grafico sem
barras, e — no caso do Ledger — crash exatamente no estado que o projeto
considera CORRETO (metrica nula porque nenhum modelo passou a ADR-007).

A correcao durradoura seria gerar os tipos do OpenAPI. Enquanto isso nao
existe, este teste compara os dois lados e falha alto.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app

TYPES_TS = Path(__file__).resolve().parents[1] / "web" / "src" / "api" / "types.ts"

# schema Pydantic -> interface TypeScript
PAIRS = {
    "RulerChannel": "StateBlock",   # a Regua consome o mesmo shape
    "AttributionShare": "AttributionBlock",
    "AttributionResponse": "AttributionResponse",
    "SourceHealth": "SourceHealth",
    "SkillMetric": "SkillMetric",
    "AnalogYear": "AnalogYear",
    "Hazard": "Hazard",
}


def _ts_fields(interface: str) -> set[str] | None:
    src = TYPES_TS.read_text(encoding="utf-8")
    m = re.search(rf"export interface {interface}\s*\{{(.*?)\n\}}", src, re.S)
    if not m:
        return None
    return set(re.findall(r"^\s*(\w+)\??:", m.group(1), re.M))


@pytest.mark.skipif(not TYPES_TS.exists(), reason="front nao instalado")
@pytest.mark.parametrize("schema_name,interface", PAIRS.items())
def test_front_types_match_api_schema(schema_name: str, interface: str):
    schemas = TestClient(app).get("/openapi.json").json()["components"]["schemas"]
    if schema_name not in schemas:
        pytest.skip(f"schema {schema_name} ausente no OpenAPI")

    api_fields = set(schemas[schema_name].get("properties", {}))
    ts_fields = _ts_fields(interface)
    assert ts_fields is not None, f"interface {interface} nao encontrada em types.ts"

    # Campo que a API envia e o front nao declara e o modo de falha real:
    # o front le uma propriedade que nao existe e recebe `undefined`.
    missing = api_fields - ts_fields
    assert not missing, (
        f"{interface} nao declara campos que a API envia: {sorted(missing)}. "
        f"API={sorted(api_fields)} TS={sorted(ts_fields)}"
    )

    # O inverso tambem quebra: o front le algo que nunca chega.
    phantom = ts_fields - api_fields
    assert not phantom, (
        f"{interface} declara campos que a API nao envia: {sorted(phantom)} — "
        "o front leria undefined em silencio"
    )
