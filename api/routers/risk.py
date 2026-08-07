"""§3 do contrato — Risco: /risk/current, /risk/hazards.

A decisao de produto mais importante do pivo (§3, ADR-013/015 em
manifests/decisions.md): o catalogo de perigos PRECISA listar `flash_flood`
com `level: null`, `basis: null`, `horizon: "synoptic"` e o encaminhamento
para Defesa Civil/SEMA-RS. Omitir esse item faria a central parecer
completa quando na verdade a engine sazonal nao sustenta nenhuma afirmacao
sobre eventos individuais (decisions.md: "Maio/2024 no RS foi bloqueio
sinotico. Nenhuma versao desta engine o teria previsto"). Por isso o
catalogo abaixo e uma constante fixa no codigo, nao derivada de dado — a
ausencia de camada sinotica e uma verdade estrutural do projeto, nao algo
que aparece ou some conforme o parquet do dia.
"""
from __future__ import annotations

from api import deps
from fastapi import APIRouter

from api.models import Hazard, HazardsCatalogResponse, RiskCurrentResponse

router = APIRouter(tags=["risk"])


def _seasonal_wet_level(oni_value: float | None) -> str:
    """Nivel do perigo sazonal `seasonal_wet_anomaly` a partir do ONI atual.

    Regra simples e auditavel (nao um modelo): El Nino desloca probabilidade
    de chuva acima da climatologia no sul do Brasil na primavera — literatura
    consolidada (CPC/INMET). Limiares seguem a classificacao operacional do
    ONI (fraco/moderado/forte) ja usada em src/state_report.py.
    """
    if oni_value is None:
        return "low"
    if oni_value >= 1.0:
        return "high"
    if oni_value >= 0.5:
        return "elevated"
    return "low"


# O ONI e MEDIDO; o nivel de perigo derivado dele NAO e. A regra acima e uma
# heuristica de literatura, nunca calibrada contra o alvo deste projeto e nunca
# submetida ao criterio da ADR-007. Declarar `basis="measured"` no nivel seria
# afirmar medicao onde ha prior — precisamente a fronteira que a engine existe
# para tornar visivel, e a falha mais cara possivel numa central de risco.
# Ate a Camada 5/6 existir, o nivel e `modeled` e carrega o proprio limite.
LEVEL_BASIS = "modeled"
UNCALIBRATED = (
    "Nivel derivado de regra heuristica sobre o ONI (limiares operacionais CPC), "
    "NAO de modelo calibrado: nenhum modelo passou o criterio da ADR-007. "
    "Desloca probabilidade de fundo; NAO indica evento individual."
)


def _hazards_catalog() -> list[Hazard]:
    headline, is_synth, source_ids = deps.state_headline()
    oni_value = headline.get("oni")
    level = _seasonal_wet_level(oni_value)
    # Dado sintetico contamina tudo a jusante; fora isso o nivel e `modeled`
    # ainda que o ONI que o alimenta seja medido.
    basis = "synthetic" if is_synth else LEVEL_BASIS

    return [
        Hazard(
            id="seasonal_wet_anomaly",
            label="Excesso de chuva sazonal OND",
            level=level,
            horizon="seasonal",
            basis=basis,
            drivers=["enso_state"],
            limits=UNCALIBRATED,
        ),
        Hazard(
            id="seasonal_dry_anomaly",
            label="Deficit de chuva sazonal OND",
            # Complementar ao excesso: so relevante do lado La Nina.
            level="elevated" if (oni_value is not None and oni_value <= -0.5) else "low",
            horizon="seasonal",
            basis=basis,
            drivers=["enso_state"],
            limits=UNCALIBRATED,
        ),
        Hazard(
            id="subseasonal_window",
            label="Janela favoravel sub-sazonal (MJO/regime)",
            # Fase 9 nao construida (decisions.md, tabela de horizontes) —
            # o catalogo declara o item, mas sem nivel: a camada nao existe.
            level=None,
            horizon="subseasonal",
            basis=None,
            drivers=[],
            limits="Fora de escopo na v1 (Fase 9, nao construida). "
                   "Nenhuma janela MJO/regime e calculada hoje.",
        ),
        Hazard(
            id="flash_flood",
            label="Cheia rapida",
            level=None,
            horizon="synoptic",
            basis=None,
            drivers=[],
            limits=(
                "Fora do escopo desta engine — exige modelo dinamico. "
                "Consulte Defesa Civil / SEMA-RS Sala de Situacao."
            ),
        ),
    ]


@router.get("/risk/hazards", response_model=HazardsCatalogResponse)
def get_hazards_catalog() -> HazardsCatalogResponse:
    return HazardsCatalogResponse(hazards=_hazards_catalog())


@router.get("/risk/current", response_model=RiskCurrentResponse)
def get_risk_current() -> RiskCurrentResponse:
    # "Ativos" = filtra o catalogo para o que tem nivel != low e != None.
    # flash_flood e subseasonal_window nunca aparecem como "ativos" porque
    # nao tem nivel a declarar — continuam visiveis so em /risk/hazards,
    # que e o catalogo completo (o "o que existe", nao "o que esta ligado").
    all_hazards = _hazards_catalog()
    active = [h for h in all_hazards if h.level not in (None, "low")]
    return RiskCurrentResponse(as_of=deps.now_iso()[:10], hazards=active)
