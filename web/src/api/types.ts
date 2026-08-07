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

export interface StateBlock {
  id: string;
  label: string;
  percentile: number;
  value: number;
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
  id: string;
  label: string;
  share_full: number;
  share_without_enso: number;
}

export interface AttributionResponse {
  season: string;
  blocks: AttributionBlock[];
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

export interface SkillMetric {
  name: string;
  point: number;
  lo: number;
  hi: number;
  permutation_null: number;
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

export interface SourceHealth {
  source_id: string;
  label: string;
  last_ingested_at: string | null;
  hash: string | null;
  status: SourceStatus;
}

export interface SourcesResponse {
  sources: SourceHealth[];
}

// ---- /meta ------------------------------------------------------------------

export interface MetaResponse {
  api_version: string;
}
