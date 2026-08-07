"""Testes da API FastAPI (docs/API_CONTRACT.md).

Foco nas garantias que o contrato torna explicitas, nao em cobertura de
linha: (1) nunca 500/tela branca mesmo sem dado real, (2) todo numero
derivado carrega provenance.basis, (3) horizon="synoptic" nunca vem com
level preenchido, (4) o catalogo de perigos declara flash_flood mesmo vazio,
(5) /state reflete o ONI real (+1.39) quando o parquet existe.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

ALL_ENDPOINTS = [
    "/api/v1/meta",
    "/api/v1/state",
    "/api/v1/state/ruler",
    "/api/v1/series/oni",
    "/api/v1/series/sam",
    "/api/v1/series/soi",
    "/api/v1/series/nino34",
    "/api/v1/series/satl",
    "/api/v1/forecast/OND2026",
    "/api/v1/forecast/OND2026/attribution",
    "/api/v1/forecast/OND2026/analogs",
    "/api/v1/risk/current",
    "/api/v1/risk/hazards",
    "/api/v1/ledger",
    "/api/v1/ledger/skill",
    "/api/v1/health/coverage",
    "/api/v1/health/breaks",
    "/api/v1/health/sources",
]


def test_every_endpoint_returns_200():
    """Regra §5.3: erro e resposta, nao excecao — nenhum endpoint pode
    devolver 500 ou qualquer coisa != 200, mesmo sem dado real disponivel.
    """
    for path in ALL_ENDPOINTS:
        r = client.get(path)
        assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:300]}"


def test_meta_has_contract_version():
    body = client.get("/api/v1/meta").json()
    assert body["contract_version"]
    assert body["api_prefix"] == "/api/v1"


def _collect_provenance_objects(obj):
    """Percorre recursivamente um payload JSON e devolve todo dict que tem
    'basis' e 'horizon' juntos (assinatura do objeto provenance do §0).
    """
    found = []
    if isinstance(obj, dict):
        if "basis" in obj and "horizon" in obj:
            found.append(obj)
        for v in obj.values():
            found += _collect_provenance_objects(v)
    elif isinstance(obj, list):
        for item in obj:
            found += _collect_provenance_objects(item)
    return found


def test_every_derived_number_has_provenance_basis():
    """§0 do contrato: todo numero derivado carrega provenance.basis. Aqui
    verificamos que todo objeto provenance encontrado nas respostas tem
    'basis' como chave presente (pode ser null explicito, nunca ausente —
    ja garantido pelo schema Pydantic, mas testamos o payload real tambem).
    """
    checked_any = False
    for path in ALL_ENDPOINTS:
        body = client.get(path).json()
        provs = _collect_provenance_objects(body)
        for p in provs:
            checked_any = True
            assert "basis" in p
            assert p["basis"] in ("measured", "modeled", "synthetic", None)
    assert checked_any, "nenhum objeto provenance encontrado nas respostas testadas"


def test_no_endpoint_returns_synoptic_horizon_with_nonnull_level():
    """§0: 'um endpoint nunca devolve horizon: synoptic' com afirmacao de
    nivel — nao ha camada que sustente isso. Verificamos especificamente nos
    hazards, que sao o unico lugar do contrato onde horizon aparece ao lado
    de level.
    """
    for path in ("/api/v1/risk/hazards", "/api/v1/risk/current"):
        body = client.get(path).json()
        for hz in body["hazards"]:
            if hz["horizon"] == "synoptic":
                assert hz["level"] is None, (
                    f"{path}: hazard {hz['id']} tem horizon=synoptic e level={hz['level']!r}"
                )


def test_hazards_catalog_includes_flash_flood_with_null_level():
    """A regra mais importante de /risk/hazards (§3): o perigo sinotico
    aparece no catalogo, level e basis explicitamente null, com
    encaminhamento externo. Omiti-lo faria a central parecer completa.
    """
    body = client.get("/api/v1/risk/hazards").json()
    ids = {h["id"]: h for h in body["hazards"]}
    assert "flash_flood" in ids, "flash_flood ausente do catalogo de hazards"
    ff = ids["flash_flood"]
    assert ff["level"] is None
    assert ff["basis"] is None
    assert ff["horizon"] == "synoptic"
    assert "Defesa Civil" in ff["limits"] or "SEMA" in ff["limits"]


def test_forecast_ond2026_is_not_accepted_with_null_rpss():
    """§2: status not_accepted com climatologia vigente e RPSS null e o
    RESULTADO correto hoje (ADR-007), nao um erro a esconder.
    """
    body = client.get("/api/v1/forecast/OND2026").json()
    assert body["status"] == "not_accepted"
    assert body["issued_at"] is None
    assert body["acceptance"]["rpss"]["point"] is None
    for target in body["targets"]:
        assert abs(sum(target["terciles"].values()) - 1.0) < 1e-6


def test_state_reflects_real_oni_when_parquet_exists():
    """data/interim/cpc_oni.parquet existe neste repo (918 linhas, MJJ/2026
    = +1.39). /state deve refletir esse valor medido, nao um placeholder.
    """
    body = client.get("/api/v1/state").json()
    assert body["headline"]["oni"] == 1.39
    assert "El Nino" in body["headline"]["classification"]
    oni_block = next(b for b in body["blocks"] if b["id"] == "oni_lag1")
    assert oni_block["provenance"]["basis"] == "measured"
    assert oni_block["value"] == 1.39


def test_resolution_warning_present_when_sample_small():
    """§1: t<30 -> resolution_warning True. As series reais aqui tem
    centenas de pontos, entao o warning deve ser False; testamos o campo
    esta presente (nao omitido) em todo bloco.
    """
    body = client.get("/api/v1/state").json()
    for block in body["blocks"]:
        assert "resolution_warning" in block
        assert isinstance(block["resolution_warning"], bool)


def test_unknown_signal_is_404_not_500():
    r = client.get("/api/v1/series/does_not_exist")
    assert r.status_code == 404


# --- fronteira medido/prior nos niveis de risco --------------------------
def test_hazard_level_is_never_declared_measured():
    """O ONI e medido; o NIVEL de perigo derivado dele nao e.

    Enquanto nenhum modelo passar a ADR-007, um nivel com basis="measured"
    afirma medicao onde ha heuristica — a falha mais cara possivel numa
    central de risco, e exatamente a fronteira que a engine existe para
    tornar visivel.
    """
    from fastapi.testclient import TestClient
    from api.main import app

    body = TestClient(app).get("/api/v1/risk/hazards").json()
    for h in body["hazards"]:
        if h.get("level") is not None:
            assert h.get("basis") != "measured", (
                f"{h['id']}: nivel {h['level']!r} declarado como medido"
            )
            assert "ADR-007" in (h.get("limits") or ""), (
                f"{h['id']}: nivel sem declaracao de que nao ha modelo calibrado"
            )
