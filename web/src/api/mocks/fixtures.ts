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
  ReferencesResponse,
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
      signal_id: 'enso_state',
      label: 'Estado ENSO',
      percentile: 0.94,
      value_current: 1.39,
      trail_12m: [0.21, 0.28, 0.35, 0.4, 0.52, 0.6, 0.68, 0.75, 0.81, 0.88, 0.91, 0.94],
      provenance: provMeasured,
    },
    {
      signal_id: 'sam_state',
      label: 'Modo Anular Sul',
      percentile: 0.22,
      value_current: -0.8,
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
  shares: [
    { block_id: 'enso', label: 'ENSO', share_full: 0.42, share_without_enso: 0 },
    { block_id: 'sam', label: 'SAM', share_full: 0.18, share_without_enso: 0.25 },
    { block_id: 'satl', label: 'Atlantico Sul', share_full: 0.15, share_without_enso: 0.2 },
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
    { metric: 'RPSS', point: 0.08, lo: -0.02, hi: 0.19, permutation_null: 0.0 },
    { metric: 'BSS', point: 0.05, lo: -0.05, hi: 0.15, permutation_null: 0.0 },
  ],
  provenance: { ...provMeasured, n_effective: 36 },
};

export const coverageFixture: CoverageResponse = {
  cells: [
    { station_id: 'prcp_a801', year: 2020, coverage_frac: 0.98 },
    { station_id: 'prcp_a801', year: 2021, coverage_frac: 0.5 },
    { station_id: 'prcp_a827', year: 2020, coverage_frac: 0.91 },
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
    { source_id: 'cpc_oni', last_ingested_at: '2026-08-01T00:00:00Z', sha256: 'a1b2c3', status: 'ok', rows: 919, notes: null },
    { source_id: 'inmet', last_ingested_at: null, sha256: null, status: 'failed', rows: null, notes: 'API instavel' },
  ],
};

export const metaFixture: MetaResponse = { api_version: 'v1' };

export const referencesFixture: ReferencesResponse = {
  version: 1,
  updated: '2026-08-07',
  reading_order: ['van_den_dool', 'ghil', 'faranda', 'gneiting', 'vera', 'cavalcanti', 'ditlevsen_p'],
  schools: [
    {
      id: 'empirica',
      label: 'Previsao empirica e analogos',
      layer: 'Camada 5 — motor preditivo',
      why: 'A camada supervisionada tem n=36.',
      people: [
        {
          id: 'van_den_dool',
          name: 'Huug van den Dool',
          affiliation: 'NOAA Climate Prediction Center',
          status: 'core',
          resolve: 'O "constructed analogue" e a forma canonica do metodo de landmarks com kernel.',
          work: 'Empirical Methods in Short-Term Climate Prediction (2007)',
        },
      ],
    },
  ],
  precedents: [
    {
      ours: 'Landmarks com kernel para previsao de estado',
      established: 'Constructed analogue',
      by: 'van_den_dool',
      note: 'Metodo classico em previsao sazonal.',
    },
  ],
};

// ---------------------------------------------------------------------------
// Dominio municipal — fixtures MINIMAS
//
// Deliberadamente pequenas: existem para que o MSW nao deixe a requisicao
// vazar e polua o teste com erro de rede. O que cada tela realmente afirma e
// testado no backend (224 testes em Python), onde o dado e real. Inflar estas
// fixtures ate parecerem a producao criaria uma segunda verdade para manter
// em sincronia — e ela divergiria na primeira mudanca de contrato.
// ---------------------------------------------------------------------------

export const municipalFixture = {
  as_of: '2026-08-08',
  provenance: {
    basis: 'modeled',
    horizon: 'seasonal',
    source_ids: ['ibge_munic_rs'],
    as_of: '2026-08-08',
    n_effective: 1,
  },
  model_card: {
    version: 'municipal-v1',
    formula: 'R = 100 * (0.38*I + 0.34*D + 0.28*E) * (0.62 + 0.38*H)',
    pesos: { impacto: 0.38, deficit: 0.34, exposicao: 0.28 },
    piso_sazonal: 0.62,
    cortes: { high: 55, elevated: 42, moderate: 28 },
    componentes: {},
    limites: ['Nao e previsao de evento.'],
    fontes: ['ibge_munic_rs'],
  },
  as_of_source: 'IBGE MUNIC 2024',
  n_total: 1,
  n_completo: 1,
  n_parcial: 0,
  n_insuficiente: 0,
  oni: 1.39,
  cenario: 'atual',
  cenario_spec: {
    label: 'Agora — ONI medido',
    horizonte: 'estado corrente',
    basis: 'measured',
    fonte: 'cpc_oni',
    nota: 'Multiplicador do ONI da ultima temporada publicada.',
    h_valor: 0.817,
    h_rotulo: 'El Nino forte',
    multiplicador: 0.93,
    saturado: false,
    leitura_saturacao: null,
  },
  municipios: [
    {
      cod_mun: 4314902,
      municipio: 'Porto Alegre',
      populacao: 1332570,
      aguas: null,
      score: 52.4,
      level: 'elevated',
      basis: 'modeled',
      completude: 'completo',
      componentes: {
        impacto: { valor: 0.8, basis: 'measured', detalhe: { atingido: true, perigos: [], danos: [] } },
        deficit_prevencao: { valor: 0.1, basis: 'measured', detalhe: { lacunas: [] } },
        exposicao: { valor: 0.99, basis: 'measured', detalhe: { grupos_expostos: [] } },
        perigo_sazonal: { valor: 0.817, basis: 'modeled', detalhe: { oni: 1.39 } },
        manutencao_ativos: { valor: null, basis: null, detalhe: { motivo: 'sem fonte publica' } },
      },
    },
  ],
};

/** Um quadrado simples: o teste nao inspeciona geometria. */
export const malhaFixture = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { codarea: '4314902' },
      geometry: {
        type: 'Polygon',
        coordinates: [[[-51.3, -30.1], [-51.1, -30.1], [-51.1, -29.9], [-51.3, -29.9], [-51.3, -30.1]]],
      },
    },
  ],
};

export const planoFixture = {
  as_of: '2026-08-08',
  provenance: {
    basis: 'modeled',
    horizon: 'seasonal',
    source_ids: ['ibge_munic_rs'],
    as_of: '2026-08-08',
    n_effective: null,
  },
  version: 'plano-v1',
  cenario: 'atual',
  n_municipios: 1,
  n_com_acao: 1,
  n_acoes_total: 1,
  n_imediatas_total: 1,
  por_acao: [
    {
      id: 'implantar_alerta',
      titulo: 'Implantar emissao de alerta a populacao',
      horizonte: 'imediato',
      esforco: 'baixo',
      fonte: 'ibge_munic_rs',
      detalhe: 'Sem alerta emitido, o resto do plano chega depois da agua.',
      n_municipios: 1,
      populacao_coberta: 1332570,
      exemplos: ['Porto Alegre'],
    },
  ],
  municipios: [],
  regras: { ordenacao: 'risco' },
  limites: ['Nao e plano de engenharia.'],
};

export const outlookFixture = {
  disponivel: true,
  autoria: 'CPC/NCEP/NWS — NOAA. Previsao EXTERNA (ADR-012).',
  basis: 'modeled',
  issued: '2026-07-09',
  alert_status: 'El Nino Advisory',
  synopsis: 'El Nino continues and will strengthen through the end of the year.',
  probabilities: [{ percent: 81, claim: 'of a very strong El Nino during October-December' }],
  next_update: '2026-08-13',
  source_url: 'https://www.cpc.ncep.noaa.gov/',
  horizonte: {
    fonte_prospectiva: 'CPC/NOAA',
    limite_util_meses: 9,
    barreira: 'barreira da primavera boreal',
    consequencia: 'Nao ha previsao ENSO defensavel para 2027.',
  },
  engine_local: {
    tem_previsao_aceita: false,
    motivo: 'nenhum modelo passou o criterio da ADR-007',
  },
};
