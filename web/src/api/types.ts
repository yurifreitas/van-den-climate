/**
 * Tipos espelhando docs/API_CONTRACT.md (v0, /api/v1).
 *
 * POR QUE espelhar a mao em vez de gerar de OpenAPI: o contrato e o
 * documento congelado (ADR-014), a API roda em paralelo e pode nao existir
 * ainda em dev — um cliente escrito a mao contra o .md e mais estavel do
 * que depender de introspeccao de um servico que pode estar fora do ar.
 */

export type Basis = 'measured' | 'modeled' | 'synthetic';
export type Horizon = 'seasonal' | 'subseasonal' | 'synoptic';

export interface Provenance {
  basis: Basis | null;
  horizon: Horizon;
  source_ids: string[];
  as_of: string;
  n_effective: number | null;
}

// ---- /state ----------------------------------------------------------

// Campos identicos ao payload: `signal_id` (nao `id`) e `value_current`
// (nao `value`). Com `id` inexistente a key do React virava undefined em
// todos os canais — React avisava de key duplicada, e a causa real era
// divergencia de contrato, nao erro de renderizacao.
export interface StateBlock {
  signal_id: string;
  label: string;
  percentile: number;
  value_current: number;
  trail_12m: number[];
  provenance: Provenance;
  resolution_warning?: boolean;
}

export interface StateResponse {
  as_of: string;
  headline: {
    oni: number;
    classification: string;
    rate_per_season: number;
  };
  blocks: StateBlock[];
}

// ---- /state/ruler ------------------------------------------------------
// Mesma forma de bloco que /state — a Regua de Surpresa consome os canais.
export interface RulerResponse {
  as_of: string;
  channels: StateBlock[];
}

// ---- /series/{signal} ---------------------------------------------------

export type SignalId = 'oni' | 'sam' | 'soi' | 'nino34' | 'satl';

export interface SeriesPoint {
  timestamp: string;
  value: number;
}

export interface SeriesResponse {
  signal: SignalId;
  points: SeriesPoint[];
  provenance: Provenance;
}

// ---- /forecast/{season} --------------------------------------------------

export interface TercileSet {
  below: number;
  normal: number;
  above: number;
}

export interface ForecastTarget {
  id: string;
  label: string;
  terciles: TercileSet;
  climatology: TercileSet;
  forecast_se?: number;
  provenance: Provenance;
}

export type ForecastStatus = 'accepted' | 'not_accepted';

export interface ForecastResponse {
  season: string;
  issued_at: string | null;
  status: ForecastStatus;
  acceptance: {
    criterion: string;
    rpss: { point: number | null; lo: number | null; hi: number | null };
    verdict: string;
  };
  targets: ForecastTarget[];
}

// ---- /forecast/{season}/attribution --------------------------------------

export interface AttributionBlock {
  block_id: string;
  label: string;
  share_full: number;
  share_without_enso: number;
}

export interface AttributionResponse {
  season: string;
  // `shares`, nao `blocks` — nome do payload real da API. O contrato nao
  // fixava este shape, entao os dois lados escolheram nomes diferentes e a
  // tela inteira quebrava com "Cannot read properties of undefined".
  shares: AttributionBlock[];
  provenance: Provenance;
}

// ---- /forecast/{season}/analogs ------------------------------------------

export interface AnalogYear {
  year: number;
  similarity: number;
  observed_tercile: number;
}

export interface AnalogsResponse {
  season: string;
  analogs: AnalogYear[];
  provenance: Provenance;
}

// ---- /risk/current, /risk/hazards ----------------------------------------

export type HazardLevel = 'low' | 'moderate' | 'elevated' | 'high' | null;

export interface Hazard {
  id: string;
  label: string;
  level: HazardLevel;
  horizon: Horizon;
  basis: Basis | null;
  drivers: string[];
  limits: string;
}

export interface RiskResponse {
  hazards: Hazard[];
}

// ---- /ledger --------------------------------------------------------------

export interface LedgerEntry {
  target_id: string;
  issued_at: string;
  predicted_tercile: 0 | 1 | 2;
  observed_tercile: 0 | 1 | 2 | null;
}

export interface LedgerResponse {
  entries: LedgerEntry[];
}

// Todos os valores sao anulaveis: enquanto nenhum modelo passar a ADR-007
// nao existe metrica a reportar, e `null` e a resposta correta.
export interface SkillMetric {
  metric: string;
  point: number | null;
  lo: number | null;
  hi: number | null;
  permutation_null: number | null;
}

export interface LedgerSkillResponse {
  target_id: string;
  metrics: SkillMetric[];
  provenance: Provenance;
}

// ---- /health/* --------------------------------------------------------------

export interface CoverageCell {
  signal_id: string;
  label: string;
  year: number;
  coverage: number;
}

export interface CoverageResponse {
  cells: CoverageCell[];
}

export interface HomogeneityBreak {
  signal_id: string;
  label: string;
  detected_at: string;
  description: string;
}

export interface BreaksResponse {
  breaks: HomogeneityBreak[];
}

export type SourceStatus = 'ok' | 'stale' | 'failed';

// Nomes iguais aos do payload da API (docs/API_CONTRACT.md §4). O contrato
// nao especificava este shape, e front e back inventaram nomes diferentes
// (`label`/`hash` vs `source_id`/`sha256`) — o TypeScript nao podia pegar,
// porque o tipo era escrito a mao e nao derivado do servidor. A tabela
// renderizava vazia sem erro nenhum.
export interface SourceHealth {
  source_id: string;
  last_ingested_at: string | null;
  sha256: string | null;
  status: SourceStatus;
  rows: number | null;
  notes: string | null;
}

export interface SourcesResponse {
  sources: SourceHealth[];
}

// ---- /meta ------------------------------------------------------------------

export interface MetaResponse {
  api_version: string;
}

// ---- /references --------------------------------------------------------

export type ReferenceStatus = 'core' | 'supporting' | 'context';

export interface ReferencePerson {
  id: string;
  name: string;
  affiliation: string | null;
  status: ReferenceStatus;
  resolve: string;
  work: string | null;
}

export interface ReferenceSchool {
  id: string;
  label: string;
  layer: string;
  why: string;
  people: ReferencePerson[];
}

export interface ReferencePrecedent {
  ours: string;
  established: string;
  by: string | null;
  note: string | null;
}

export interface ReferencesResponse {
  version: number;
  updated: string;
  reading_order: string[];
  schools: ReferenceSchool[];
  precedents: ReferencePrecedent[];
}
