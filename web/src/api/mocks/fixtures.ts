/**
 * Exemplos fieis ao docs/API_CONTRACT.md — usados pelo MSW (dev/teste) e
 * pelos testes de tipos/render. Mantenha em sincronia manual com o .md;
 * nao ha geracao automatica porque o contrato e o documento fonte, nao um
 * schema publicado (ADR-014).
 */
import type {
  AnalogsResponse,
  AttributionResponse,
  BreaksResponse,
  CoverageResponse,
  ForecastResponse,
  LedgerResponse,
  LedgerSkillResponse,
  MetaResponse,
  RiskResponse,
  RulerResponse,
  SeriesResponse,
  SourcesResponse,
  StateResponse,
} from '../types';

const provMeasured = {
  basis: 'measured' as const,
  horizon: 'seasonal' as const,
  source_ids: ['cpc_oni'],
  as_of: '2026-08-07T12:33:47Z',
  n_effective: 36,
};

export const stateFixture: StateResponse = {
  as_of: '2026-06-01',
  headline: { oni: 1.39, classification: 'El Nino moderado', rate_per_season: 0.43 },
  blocks: [
    {
      id: 'enso_state',
      label: 'Estado ENSO',
      percentile: 0.94,
      value: 1.39,
      trail_12m: [0.21, 0.28, 0.35, 0.4, 0.52, 0.6, 0.68, 0.75, 0.81, 0.88, 0.91, 0.94],
      provenance: provMeasured,
    },
    {
      id: 'sam_state',
      label: 'Modo Anular Sul',
      percentile: 0.22,
      value: -0.8,
      trail_12m: [0.5, 0.48, 0.44, 0.4, 0.38, 0.35, 0.3, 0.28, 0.26, 0.25, 0.23, 0.22],
      provenance: { ...provMeasured, source_ids: ['noaa_sam'], n_effective: 24 },
    },
  ],
};

export const rulerFixture: RulerResponse = {
  as_of: '2026-06-01',
  channels: stateFixture.blocks,
};

export const seriesOniFixture: SeriesResponse = {
  signal: 'oni',
  points: Array.from({ length: 24 }, (_, i) => ({
    timestamp: `2024-${String((i % 12) + 1).padStart(2, '0')}-01`,
    value: Math.sin(i / 3) * 1.5,
  })),
  provenance: provMeasured,
};

export const forecastNotAcceptedFixture: ForecastResponse = {
  season: 'OND2026',
  issued_at: null,
  status: 'not_accepted',
  acceptance: {
    criterion: 'lower bound of 90% CI of RPSS > 0',
    rpss: { point: null, lo: null, hi: null },
    verdict: 'climatology remains in force',
  },
  targets: [
    {
      id: 'wetday_freq',
      label: 'Frequencia de dias umidos',
      terciles: { below: 0.33, normal: 0.33, above: 0.34 },
      climatology: { below: 0.33, normal: 0.33, above: 0.33 },
      provenance: { ...provMeasured },
    },
    {
      id: 'intensity',
      label: 'Intensidade media',
      terciles: { below: 0.3, normal: 0.35, above: 0.35 },
      climatology: { below: 0.33, normal: 0.33, above: 0.33 },
      provenance: { ...provMeasured },
    },
    {
      id: 'p95',
      label: 'Percentil 95 de precipitacao',
      terciles: { below: 0.28, normal: 0.34, above: 0.38 },
      climatology: { below: 0.33, normal: 0.33, above: 0.33 },
      provenance: { ...provMeasured },
    },
  ],
};

export const attributionFixture: AttributionResponse = {
  season: 'OND2026',
  blocks: [
    { id: 'enso', label: 'ENSO', share_full: 0.42, share_without_enso: 0 },
    { id: 'sam', label: 'SAM', share_full: 0.18, share_without_enso: 0.25 },
    { id: 'satl', label: 'Atlantico Sul', share_full: 0.15, share_without_enso: 0.2 },
  ],
  provenance: provMeasured,
};

export const analogsFixture: AnalogsResponse = {
  season: 'OND2026',
  analogs: [
    { year: 2015, similarity: 0.91, observed_tercile: 2 },
    { year: 1997, similarity: 0.87, observed_tercile: 2 },
    { year: 2009, similarity: 0.79, observed_tercile: 1 },
  ],
  provenance: provMeasured,
};

export const riskFixture: RiskResponse = {
  hazards: [
    {
      id: 'seasonal_wet_anomaly',
      label: 'Excesso de chuva sazonal OND',
      level: 'elevated',
      horizon: 'seasonal',
      basis: 'measured',
      drivers: ['enso_state'],
      limits: 'Desloca probabilidade de fundo. NAO indica evento individual.',
    },
    {
      id: 'flash_flood',
      label: 'Cheia rapida',
      level: null,
      horizon: 'synoptic',
      basis: null,
      drivers: [],
      limits:
        'Fora do escopo desta engine — exige modelo dinamico. Consulte Defesa Civil / SEMA-RS Sala de Situacao.',
    },
  ],
};

export const ledgerFixture: LedgerResponse = {
  entries: [
    { target_id: 'wetday_freq', issued_at: '2023-09-01', predicted_tercile: 2, observed_tercile: 2 },
    { target_id: 'wetday_freq', issued_at: '2022-09-01', predicted_tercile: 1, observed_tercile: 0 },
    { target_id: 'wetday_freq', issued_at: '2021-09-01', predicted_tercile: 0, observed_tercile: 0 },
  ],
};

export const ledgerSkillFixture: LedgerSkillResponse = {
  target_id: 'wetday_freq',
  metrics: [
    { name: 'RPSS', point: 0.08, lo: -0.02, hi: 0.19, permutation_null: 0.0 },
    { name: 'BSS', point: 0.05, lo: -0.05, hi: 0.15, permutation_null: 0.0 },
  ],
  provenance: { ...provMeasured, n_effective: 36 },
};

export const coverageFixture: CoverageResponse = {
  cells: [
    { signal_id: 'prcp_a801', label: 'Porto Alegre', year: 2020, coverage: 0.98 },
    { signal_id: 'prcp_a801', label: 'Porto Alegre', year: 2021, coverage: 0.5 },
    { signal_id: 'prcp_a827', label: 'Caxias do Sul', year: 2020, coverage: 0.91 },
  ],
};

export const breaksFixture: BreaksResponse = {
  breaks: [
    {
      signal_id: 'prcp_a801',
      label: 'Porto Alegre',
      detected_at: '2005-01-01',
      description: 'Transicao convencional -> automatica (INMET)',
    },
  ],
};

export const sourcesFixture: SourcesResponse = {
  sources: [
    { source_id: 'cpc_oni', label: 'CPC ONI', last_ingested_at: '2026-08-01T00:00:00Z', hash: 'a1b2c3', status: 'ok' },
    { source_id: 'inmet', label: 'INMET', last_ingested_at: null, hash: null, status: 'failed' },
  ],
};

export const metaFixture: MetaResponse = { api_version: 'v1' };
