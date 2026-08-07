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
  station_id: string;
  year: number;
  coverage_frac: number;
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

// Leituras adversariais: trabalho que, se estiver certo, ENFRAQUECE uma
// premissa do projeto. Nomes de campo exatamente iguais ao payload da API
// (claim, challenge, by, consequence) — tests/test_contract_sync.py compara
// esta interface contra o schema OpenAPI real e falha se renomear.
export interface ReferenceAdversarial {
  claim: string;
  challenge: string;
  by: string | null;
  consequence: string;
}

export interface ReferencesResponse {
  version: number;
  updated: string;
  reading_order: string[];
  schools: ReferenceSchool[];
  precedents: ReferencePrecedent[];
  adversarial?: ReferenceAdversarial[];
}

// ---- /risk/municipal -------------------------------------------------

export type NivelRisco = 'low' | 'moderate' | 'elevated' | 'high';
export type Completude = 'completo' | 'parcial' | 'insuficiente';

/**
 * Um componente do indice, com proveniencia PROPRIA — o indice municipal
 * mistura medido (impacto e deficit, declarados pela prefeitura ao IBGE) com
 * modelado (perigo sazonal) e com ausencia declarada (manutencao de ativos).
 * `valor: null` + `basis: null` e estado legitimo; ver `detalhe.motivo`.
 */
export interface ComponenteRisco {
  valor: number | null;
  basis: Basis | null;
  detalhe: {
    motivo?: string;
    atingido?: boolean;
    perigos?: string[];
    danos?: string[];
    score_perigos?: number;
    score_danos?: number;
    plano_contingencia?: boolean | null;
    plano_executado?: boolean | null;
    alerta_emitido?: boolean | null;
    lacunas?: string[];
    populacao_percentil?: number | null;
    grupos_expostos?: string[];
    oni?: number | null;
    rotulo?: string;
    escopo?: string;
  };
}

/**
 * Memoria hidrica do municipio (JRC 1984-2021). Dimensao PARALELA: nao entra
 * no indice composto porque agua sazonal de satelite nao separa banhado de
 * lavoura de arroz irrigada. `null` quando a camada nao foi calculada.
 */
export interface AguasMunicipio {
  permanente: { km2: number | null; frac: number | null };
  sazonal: { km2: number | null; frac: number | null };
  perdida: { km2: number | null; frac: number | null };
  efemera: { km2: number | null; frac: number | null };
  area_grade_km2: number | null;
  memoria_hidrica_km2: number;
  memoria_hidrica_frac: number | null;
  basis: Basis;
}

export interface AguasMeta {
  disponivel: boolean;
  motivo?: string;
  basis?: Basis;
  produto?: string;
  janela?: string;
  nao_cobre?: string;
  recorte?: string;
  area_estado_km2?: number;
  total_km2?: Record<string, number>;
  referencia?: string;
  limites?: string[];
  overlay?: {
    png: string;
    bbox: { lon_min: number; lon_max: number; lat_min: number; lat_max: number };
    cores: Record<string, number[]>;
    ordem_pintura: string[];
  };
}

// ---- /resposta/municipios --------------------------------------------

/** Escala ordinal do MUNIC traduzida. `aplicavel: false` = nao foi testado. */
export interface EscalaLogistica {
  id: string;
  rotulo: string;
  resposta: string | null;
  valor: number | null;
  aplicavel: boolean;
}

export interface MunicipioResposta {
  cod_mun: number;
  municipio: string;
  populacao: number | null;
  /** `unidade` e sempre "estabelecimentos" — NUNCA leitos. Ver `lacunas`. */
  capacidade: {
    unidade: string;
    total: number;
    hospitais: number;
    urgencia: number;
    centro_cirurgico: number;
    centro_obstetrico: number;
    por_100k: number | null;
    km_ate_unidade_mais_proxima: number | null;
    basis: Basis | null;
  };
  vulneraveis: { grupos: string[]; n_respondidos: number; basis: Basis | null };
  saude: { impactos: string[]; n_respondidos: number; basis: Basis | null };
  resposta: {
    prestadas: string[];
    n_respondidos: number;
    apoio_psicologico: boolean | null;
    basis: Basis | null;
  };
  autonomia_logistica: {
    indice: number | null;
    n_aplicaveis: number;
    itens: EscalaLogistica[];
    basis: Basis | null;
  };
}

export interface RespostaResponse {
  as_of: string;
  provenance: Provenance;
  resumo: {
    version: string;
    n_municipios: number;
    capacidade: {
      unidade: string;
      aviso: string;
      total_estabelecimentos: number;
      municipios_sem_unidade: number;
      km_mediano_ate_unidade: number | null;
    };
    saude_afetada: number;
    apoio_psicologico: { ofereceram: number; nao_ofereceram: number };
    autonomia: { n_avaliados: number; mediana: number | null };
    fora_do_indice: string;
  };
  /** Lacunas declaradas: leitos, dias letivos, recuperacao financeira... */
  lacunas: { id: string; titulo: string; motivo: string }[];
  municipios: MunicipioResposta[];
}

export interface CruzamentoAguas {
  as_of: string;
  n_com_memoria_e_inundacao: number;
  criterio: string;
  independencia: string;
  municipios: {
    cod_mun: number;
    municipio: string;
    memoria_hidrica_frac: number | null;
    memoria_hidrica_km2: number;
    agua_perdida_km2: number | null;
    perigos_2024: string[];
    score: number | null;
    level: NivelRisco | null;
  }[];
}

export interface MunicipioRisco {
  cod_mun: number;
  municipio: string;
  populacao: number | null;
  aguas: AguasMunicipio | null;
  /** null quando a cobertura de dado nao alcanca o minimo do modelo. Nunca 0. */
  score: number | null;
  level: NivelRisco | null;
  basis: Basis | null;
  completude: Completude;
  componentes: {
    impacto: ComponenteRisco;
    deficit_prevencao: ComponenteRisco;
    exposicao: ComponenteRisco;
    perigo_sazonal: ComponenteRisco;
    manutencao_ativos: ComponenteRisco;
  };
}

export interface ModelCard {
  version: string;
  formula: string;
  pesos: Record<string, number>;
  piso_sazonal: number;
  cortes: Record<string, number>;
  componentes: Record<string, string>;
  limites: string[];
  fontes: string[];
}

/** Horizonte do indice. `estrutural` e o unico defensavel para 2027+. */
export type Cenario = 'atual' | 'ond2026' | 'estrutural';

export interface CenarioSpec {
  label: string;
  horizonte: string;
  basis: Basis | null;
  fonte: string;
  nota: string;
  h_valor: number;
  h_rotulo: string;
  multiplicador: number;
  saturado: boolean;
  leitura_saturacao: string | null;
  oni_ancora?: number;
}

export interface MunicipalRiskResponse {
  as_of: string;
  provenance: Provenance;
  model_card: ModelCard;
  as_of_source: string;
  n_total: number;
  n_completo: number;
  n_parcial: number;
  n_insuficiente: number;
  oni: number | null;
  cenario: Cenario;
  cenario_spec: CenarioSpec;
  municipios: MunicipioRisco[];
}

// ---- /outlook/enso ---------------------------------------------------

/**
 * Boletim ENSO do CPC/NOAA. A previsao e EXTERNA (ADR-012: contexto, nunca
 * feature) — `engine_local.tem_previsao_aceita` continua false porque nenhum
 * modelo desta engine passou a ADR-007.
 */
export interface OutlookResponse {
  disponivel: boolean;
  motivo?: string;
  autoria?: string;
  basis?: Basis;
  issued?: string;
  alert_status?: string;
  synopsis?: string;
  probabilities?: { percent: number; claim: string }[];
  next_update?: string | null;
  source_url?: string;
  horizonte?: {
    fonte_prospectiva: string;
    limite_util_meses: number;
    barreira: string;
    consequencia: string;
  };
  engine_local?: { tem_previsao_aceita: boolean; motivo: string };
}

/** GeoJSON da malha do IBGE — `properties.codarea` e o codigo do municipio. */
export interface MalhaFeature {
  type: 'Feature';
  properties: { codarea: string };
  geometry: {
    type: 'Polygon' | 'MultiPolygon';
    coordinates: number[][][] | number[][][][];
  };
}

export interface MalhaResponse {
  type: 'FeatureCollection';
  features: MalhaFeature[];
}
