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
    # A ingestao ser recente NAO significa que o dado seja recente: o GHCN foi
    # baixado hoje e a serie termina em 1999. Sem separar as duas coisas, o
    # painel de saude dizia "ok" para um arquivo parado ha 27 anos.
    # None = serie corrente, acompanha o calendario.
    cobertura_ate: str | None = None
    idade_dias: int | None = None
    vence_em: str | None = None


class SourcesHealthResponse(BaseModel):
    sources: list[SourceStatus]


class MetaResponse(BaseModel):
    contract_version: str
    api_prefix: str
    generated_at: str


# ---------------------------------------------------------------------------
# Catalogo de referencias (manifests/references.yaml) — nao faz parte do
# contrato v0 congelado (docs/API_CONTRACT.md); e um endpoint auxiliar que
# serve, estruturado, o catalogo de leitura curado do projeto.
# ---------------------------------------------------------------------------

ReferenceStatus = Literal["core", "supporting", "context"]


class ReferencePerson(BaseModel):
    id: str
    name: str
    affiliation: str | None = None
    status: ReferenceStatus
    resolve: str
    work: str | None = None


class ReferenceSchool(BaseModel):
    id: str
    label: str
    layer: str
    why: str
    people: list[ReferencePerson]


class ReferencePrecedent(BaseModel):
    ours: str
    established: str
    by: str | None = None
    note: str | None = None


class ReferenceAdversarial(BaseModel):
    """Leitura que, se estiver certa, ENFRAQUECE uma premissa do projeto.

    Existe porque um projeto com n=36 se convence de coisas falsas lendo so
    quem concorda. Servir isto ao lado do catalogo e deliberado.
    """

    claim: str          # a premissa nossa que esta sob ataque
    challenge: str      # o argumento contrario
    by: str | None      # id da pessoa/escola que o sustenta
    consequence: str    # o que muda no projeto se proceder


class ReferencesResponse(BaseModel):
    version: int
    updated: str
    reading_order: list[str]
    schools: list[ReferenceSchool]
    precedents: list[ReferencePrecedent]
    adversarial: list[ReferenceAdversarial] = []


# ---------------------------------------------------------------------------
# §3b Risco municipal — prioridade preventiva por municipio
# ---------------------------------------------------------------------------

class Componente(BaseModel):
    """Um componente do indice, com proveniencia PROPRIA.

    O `basis` mora aqui, e nao so no envelope, porque o indice municipal
    mistura naturezas: impacto e deficit sao medidos (declaracao da prefeitura
    ao IBGE), perigo sazonal e modelado, e manutencao de ativos e uma ausencia
    declarada. Um unico `basis` no topo apagaria essa diferenca, que e
    precisamente a informacao que o §0 do contrato existe para preservar.

    `valor=None` com `basis=None` e estado legitimo: a base nao responde por
    este municipio. Ver `detalhe.motivo`.
    """

    valor: float | None = None
    basis: Basis | None = None
    detalhe: dict = Field(default_factory=dict)


class ComponentesMunicipais(BaseModel):
    impacto: Componente
    deficit_prevencao: Componente
    exposicao: Componente
    perigo_sazonal: Componente
    # Sempre presente, sempre vazio ate existir fonte. Declarar a lacuna no
    # contrato e o que impede que ela seja esquecida: um campo ausente parece
    # um campo que ninguem precisou, um campo nulo com motivo e uma divida.
    manutencao_ativos: Componente


class MunicipalRow(BaseModel):
    cod_mun: int
    municipio: str
    populacao: int | None = None
    # Memoria hidrica (JRC 1984-2021). Dimensao PARALELA: anexada a linha mas
    # deliberadamente fora do indice composto — agua sazonal de satelite nao
    # separa banhado de arroz irrigado. Ver `model_card.memoria_hidrica`.
    # None quando a camada nao foi calculada; nunca zeros.
    aguas: dict | None = None
    # None quando a cobertura de dado nao alcanca o minimo do modelo. Nunca 0:
    # zero afirmaria "avaliado e sem risco", que e uma afirmacao diferente.
    score: float | None = None
    level: Literal["low", "moderate", "elevated", "high"] | None = None
    basis: Basis | None = None
    completude: Literal["completo", "parcial", "insuficiente"]
    componentes: ComponentesMunicipais


class MunicipalRiskResponse(BaseModel):
    as_of: str
    provenance: Provenance
    # Ficha do modelo (pesos, formula, cortes, limites) no proprio payload:
    # indice composto sem os pesos publicados nao e auditavel.
    model_card: dict
    as_of_source: str
    n_total: int
    n_completo: int
    n_parcial: int
    n_insuficiente: int
    oni: float | None = None
    # Horizonte escolhido: atual | ond2026 | estrutural. `cenario_spec` traz o
    # multiplicador aplicado, a fonte e — quando o multiplicador satura em
    # 1.00 — a leitura de que a previsao nao aplica nenhum desconto.
    cenario: str = "atual"
    cenario_spec: dict = Field(default_factory=dict)
    municipios: list[MunicipalRow]


class MunicipalDetailResponse(BaseModel):
    as_of: str
    provenance: Provenance
    posicao: int | None = None
    n_ranqueados: int
    municipio: MunicipalRow
    model_card: dict
