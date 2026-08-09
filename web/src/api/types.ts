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

/**
 * Precedente construtivo atipico: obra ou pratica real que ataca um mecanismo
 * do catalogo de contencao por um caminho fora do repertorio padrao.
 *
 * `limite` e obrigatorio no tipo porque e obrigatorio na leitura — a interface
 * nao tem permissao de mostrar a obra sem mostrar onde ela nao resolve.
 */
export interface ReferenceConstrutiva {
  id: string;
  titulo: string;
  onde: string;
  quando: string;
  mecanismo: string;
  /** ids de estrategia em src/risk/contencao.py */
  aplicavel_a: string[];
  por_que_atipica: string;
  limite: string;
  fonte: string;
}

export interface ReferencesResponse {
  version: number;
  updated: string;
  reading_order: string[];
  schools: ReferenceSchool[];
  precedents: ReferencePrecedent[];
  adversarial?: ReferenceAdversarial[];
  construtivos?: ReferenceConstrutiva[];
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

// ---- /dossie/{cod_mun} -----------------------------------------------

/**
 * As dez camadas reunidas na ordem da DECISAO, nao da construcao.
 * Cada bloco carrega `basis` proprio: achatar num selo unico apagaria a
 * diferenca entre medido, modelado e inexistente.
 */
export interface DossieResponse {
  as_of: string;
  provenance: Provenance;
  version: string;
  cod_mun: number;
  municipio: string;
  cenario: Cenario;
  posicao: {
    indice: number | null;
    nivel: NivelRisco | null;
    basis: Basis | null;
    completude: Completude;
    posicao_no_ranking: number | null;
    de: number;
    populacao: number | null;
    regime_cheia: { regime: string | null; bacia: string | null } | null;
  };
  perigo: {
    componentes: MunicipioRisco['componentes'];
    memoria_hidrica: AguasMunicipio | null;
    geotecnico: { score: number | null; ocorrencias: string[]; basis: Basis | null } | null;
    acesso: {
      score: number | null;
      ocorrencias: string[];
      ficou_ilhado: boolean | null;
      dano_viario: boolean | null;
      basis: Basis | null;
    } | null;
    barragem: { dano_declarado: boolean | null; basis: Basis | null; nota: string } | null;
    /** Fracao de MUNICIPIO, nao de bacia — proxy ordinal, limiar = percentil 90 do RS. */
    impermeabilizacao: {
      frac_construida: number | null;
      limiar_rs: number | null;
      acima_do_limiar: boolean | null;
      basis: Basis | null;
      nota: string;
    } | null;
  };
  exposicao: {
    populacao: number | null;
    grupos_vulneraveis: { grupos: string[]; n_respondidos: number; basis: Basis | null } | null;
    territorios_tradicionais: {
      tipo: string;
      nome: string | null;
      grupo_etnico: string | null;
      situacao_juridica: string | null;
      area_legal_ha: number | null;
      memoria_hidrica_frac: number | null;
      km_ate_urgencia: number | null;
    }[];
    n_territorios: number;
  };
  capacidade: {
    saude: MunicipioResposta['capacidade'] | null;
    cobertura_recursos: Record<string, { n_no_municipio: number; km_mais_proximo: number | null }> | null;
    pontes: { n_malha_principal: number; n_estruturantes: number; nota: string } | null;
    quadro_pessoal: PessoalResponse['municipios'][number]['quadro'] | null;
    voluntariado: { km_brigada_mais_proxima: number | null; tem_no_municipio: boolean } | null;
  };
  falhas_2024: {
    deficit_prevencao: ComponenteRisco;
    autonomia_logistica: MunicipioResposta['autonomia_logistica'] | null;
    saude_afetada: MunicipioResposta['saude'] | null;
    resposta_prestada: MunicipioResposta['resposta'] | null;
    faltou_pessoal: boolean | null;
  };
  acao: {
    n_acoes: number;
    n_imediatas: number;
    acoes: AcaoPlano[];
    estrategias_contencao: {
      id: string;
      titulo: string;
      mecanismo: string;
      evidencia: string;
      convencional: string;
      natureza: string;
      quando_natureza_ganha: string;
      limite: string;
      basis: Basis;
    }[];
  };
  /** NAO e rodape: quem decide sem saber o que falta decide pior. */
  lacunas: { camada: string; id: string; titulo: string; motivo: string }[];
}

// ---- /pessoal --------------------------------------------------------

export interface PessoalResponse {
  as_of: string;
  provenance: Provenance;
  resumo: {
    version: string;
    n_municipios: number;
    n_com_quadro: number;
    servidores_por_mil: { mediana: number | null; min: number | null; max: number | null; nota: string };
    quadro_fragil: { n: number; limiar: number; definicao: string };
    sem_concurso_24m: number;
    faltou_pessoal_em_2024: number;
    voluntariado: {
      n_brigadas_identificadas: number;
      municipios_a_mais_de_60km: number;
      /** O achado que organiza a estrategia: o modelo ja existe no RS. */
      modelo_existente: string;
      municipios_com_brigada: string[];
    };
    limites: string[];
  };
  /** Sugere COM QUEM CONVERSAR — nunca afirma que o vizinho tem gente sobrando. */
  auxilio_mutuo: {
    cod_mun: number;
    municipio: string;
    score: number | null;
    level: NivelRisco | null;
    motivos: string[];
    vizinhos_com_folga: { cod_mun: number; municipio: string; km: number; servidores_por_mil: number | null }[];
  }[];
  municipios: {
    cod_mun: number;
    municipio: string;
    populacao: number | null;
    quadro: {
      total: number | null;
      estatutarios: number | null;
      sem_vinculo: number | null;
      estagiarios: number | null;
      por_mil_hab: number | null;
      percentil_por_mil: number | null;
      frac_sem_estabilidade: number | null;
      quadro_fragil: boolean | null;
      concurso_24m: boolean | null;
      basis: Basis | null;
    };
    voluntariado: { km_brigada_mais_proxima: number | null; tem_no_municipio: boolean; basis: Basis | null };
    faltou_pessoal_em_2024: boolean | null;
  }[];
}

// ---- /recursos -------------------------------------------------------

/**
 * Quao completa e a FONTE do recurso — distinta de `Completude`, que mede
 * quanto de dado um municipio tem no indice. Sem esta distincao, um vazio do
 * OpenStreetMap parece um vazio real do territorio.
 */
export type CompletudeFonte = 'cadastro' | 'cadastro_parcial' | 'colaborativa';

export interface PapelRecurso {
  label: string;
  fonte: string;
  completude: CompletudeFonte;
  /** Papeis nao se somam entre familias — ver o comentario em recursos.py. */
  familia: string;
  n: number;
  municipios_alem_do_limiar: number | null;
  n_expostos_a_agua: number | null;
}

/**
 * Cruzamento de cada recurso com a memoria hidrica do JRC (1984-2021).
 *
 * Um mapa de recursos responde "onde estao"; isto responde a pergunta que
 * 2024 fez no RS: quais deles saem de operacao junto com o evento. Hospital
 * que alaga nao e capacidade — vira demanda, no pior momento possivel.
 */
export interface ExposicaoHidrica {
  limiar_frac_celula: number;
  n_expostos: number;
  n_avaliados: number;
  taxa_por_familia: Record<
    string,
    { label: string; n: number; n_expostos: number; taxa: number | null }
  >;
  criticos_expostos: {
    id: string;
    papel: string;
    label: string;
    nome: string | null;
    cod_mun_proximo: number;
    memoria_hidrica_frac: number;
    fonte: string;
  }[];
  nota: string;
}

/** Municipio onde risco alto encontra recurso critico distante. */
export interface VazioCobertura {
  cod_mun: number;
  municipio: string;
  score: number | null;
  level: NivelRisco | null;
  populacao: number | null;
  faltas: { papel: string; label: string; km: number | null; completude: CompletudeFonte }[];
  pior_km: number;
}

export interface RecursosResponse {
  as_of: string;
  provenance: Provenance;
  resumo: {
    version: string;
    total_pontos: number;
    por_papel: Record<string, PapelRecurso>;
    limiar_vazio_km: number;
    subtipos_moveis: Record<string, number>;
    familias: Record<string, string>;
    exposicao_hidrica: ExposicaoHidrica;
    municipios_sem_abrigo_mapeado: number;
    ressalvas: string[];
  };
  /**
   * A lista de vazios vem ENVELOPADA, e nao como array solto.
   *
   * O cadastro de recursos e medido — cada ponto foi observado. A ORDEM desta
   * lista nao e: ela cruza o indice de prioridade (modelado) com a distancia
   * ao recurso mais proximo (medida). Selar as duas coisas com o mesmo
   * `provenance` do topo afirmaria medicao onde ha composicao, entao a lista
   * carrega selo e nota proprios.
   *
   * Isto ja quebrou a demo uma vez: a API passou a envelopar, este tipo
   * continuou dizendo `[]`, o TypeScript concordou com a mentira e a tela
   * so morreu em producao, com `s.map is not a function`. Tipo escrito a mao
   * contra o contrato nao e verificacao — por isso existe
   * `RecursosView.test.tsx`, que renderiza contra o snapshot real.
   */
  vazios: {
    provenance: Provenance;
    nota: string;
    itens: VazioCobertura[];
  };
  pontos: { id: string; papel: string; nome: string | null; subtipo: string | null; lat: number; lon: number; fonte: string }[];
  por_municipio: Record<string, Record<string, { n_no_municipio: number; km_mais_proximo: number | null; completude: CompletudeFonte }>>;
}

// ---- /plano ----------------------------------------------------------

/** Uma acao e sua evidencia. `evidencia` e o campo exato que a disparou. */
export interface AcaoPlano {
  id: string;
  titulo: string;
  horizonte: 'imediato' | 'estrutural';
  esforco: 'baixo' | 'medio' | 'alto';
  fonte: string;
  detalhe: string;
  evidencia: string;
  basis: Basis;
}

export interface AcaoAgregada {
  id: string;
  titulo: string;
  horizonte: 'imediato' | 'estrutural';
  esforco: 'baixo' | 'medio' | 'alto';
  fonte: string;
  detalhe: string;
  n_municipios: number;
  populacao_coberta: number;
  exemplos: string[];
}

export interface PlanoResponse {
  as_of: string;
  provenance: Provenance;
  version: string;
  cenario: Cenario;
  n_municipios: number;
  n_com_acao: number;
  n_acoes_total: number;
  n_imediatas_total: number;
  por_acao: AcaoAgregada[];
  municipios: {
    cod_mun: number;
    municipio: string;
    score: number | null;
    level: NivelRisco | null;
    populacao: number | null;
    n_acoes: number;
    n_imediatas: number;
    acoes: AcaoPlano[];
  }[];
  regras: Record<string, string | number>;
  limites: string[];
}

// ---- /historico/chuva ------------------------------------------------

export interface DeslocamentoMetrica {
  delta: number;
  ic90: [number, number];
  /** IC 90% nao cruza zero — mesmo espirito do criterio da ADR-007. */
  separa_de_zero: boolean;
}

export interface FaseMetrica {
  media: number;
  ic90: [number, number];
}

export interface HistoricoResponse {
  disponivel: boolean;
  motivo?: string;
  basis?: Basis;
  meta?: {
    version: string;
    fonte: string;
    n_estacoes: number;
    n_temporadas_estacao: number;
    periodo: [number, number];
    periodo_com_oni: [number, number] | null;
    estacao_alvo: string;
    limiar_dia_umido_mm: number;
    cobertura_minima_dias: number;
    contato_com_alvo: string;
    limites: string[];
  };
  composto?: {
    limiar_oni: number;
    fases: Record<string, { n_anos: number; anos: number[] } & Record<string, FaseMetrica>>;
    deslocamento_elnino_vs_neutro?: Record<string, DeslocamentoMetrica>;
  };
  por_ano?: {
    ano: number;
    n_estacoes: number;
    freq_dias_umidos: number;
    intensidade_mm: number;
    p95_mm: number;
    total_mm: number;
    oni_ond: number | null;
    fase: string;
  }[];
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

// ---- /terreno --------------------------------------------------------

/**
 * No que a chuva cai. As duas camadas viajam juntas porque leem o mesmo
 * cruzamento de solo, cobertura e relevo — separa-las obrigaria a varrer o
 * cruzamento duas vezes por consulta.
 *
 * O envelope inteiro e `modeled`, sem excecao. A fracao de solo e cobertura
 * por baixo e medida (IBGE/BDiA), mas tudo que chega aqui passou por
 * traducao: ordem do SiBCS para grupo hidrologico, par (grupo, cobertura)
 * para Curve Number, serie diaria para chuva de projeto.
 */
export interface EventoChuva {
  tr_anos: number;
  p24h_mm: number;
  escoamento_mm: number;
  /** Mesma chuva com o perfil ja cheio (AMC III) — o caso do desastre. */
  escoamento_mm_solo_umido: number;
  coef_escoamento: number | null;
  volume_hm3: number;
}

export interface MunicipioHidrologia {
  cod_mun: number;
  municipio: string;
  area_km2: number;
  cn2: number;
  cn3_solo_umido: number;
  cn_solo_sem_impermeavel: number;
  frac_construida: number | null;
  s_mm: number;
  grupos_hidrologicos: Record<string, number>;
  cobertura: Record<string, number>;
  /** Ordinal, nunca minutos: sem talvegue nao existe tempo de concentracao. */
  resposta: string | null;
  resposta_escore: number | null;
  /** Declividade MEDIDA (Copernicus DEM 90 m), nao o adjetivo da carta. */
  declividade_media_pct: number | null;
  relevo_medido: boolean;
  estacao_chuva: { station_id: string; nome: string; km: number; anos: number } | null;
  eventos: EventoChuva[];
  unidade_geomorfologica: string | null;
}

export interface MunicipioDegradacao {
  cod_mun: number;
  municipio: string;
  area_km2: number;
  /** Indice da equacao sob P=1, nao tonelada perdida. O nome carrega isso. */
  indice_rusle_t_ha_ano: number;
  classe: string;
  percentil_rs: number;
  km2_uso_intensivo_em_declive: number;
  frac_uso_intensivo_em_declive: number;
  km2_solo_raso_sob_uso_intensivo: number;
  km2_cobertura_permanente_em_declive: number;
  /** LS calculado sobre declividade medida; `null` sem DEM ingerido. */
  ls_medido_dem: number | null;
  ls_reancorado: boolean;
  /** LS medido / LS da carta. Acima de 1, a carta subestimou o relevo. */
  fator_reancoragem: number | null;
  erosividade_r: number | null;
  estacao_chuva: { station_id: string; nome: string; km: number; chuva_anual_mm: number } | null;
  onde_mais_perde: {
    solo: string | null;
    relevo: string | null;
    cobertura: string;
    km2: number;
    indice_t_ha_ano: number;
  }[];
}

export interface RegiaoHidrologica {
  unidade: string;
  n_municipios: number;
  area_km2: number;
  cn2_medio: number | null;
  municipios_cn_alto: string[];
}

export interface TerrenoResponse {
  as_of: string;
  provenance: Provenance;
  hidrologia: {
    resumo: {
      version: string;
      n_municipios: number;
      razao_ia: number;
      tr_anos: number[];
      cn2_mediano: number | null;
      cn2_p90: number;
      n_estacoes_chuva: number;
      avisos: Record<string, number>;
    };
    limites: string[];
    regioes: RegiaoHidrologica[];
    municipios: MunicipioHidrologia[];
    n_total: number;
  };
  degradacao: {
    resumo: {
      version: string;
      n_municipios: number;
      indice_mediano_t_ha_ano: number | null;
      p_assumido: number;
      comprimento_rampa_assumido_m: number;
      km2_uso_intensivo_em_declive_rs: number;
      km2_solo_raso_sob_uso_intensivo_rs: number;
      nota_escala: string;
    };
    limites: string[];
    municipios: MunicipioDegradacao[];
    n_total: number;
  };
  /**
   * Condicao de umidade antecedente vigente, com chuva observada ate ontem.
   *
   * Selo proprio dentro de um envelope `modeled`: a chuva de cinco dias e
   * OBSERVACAO (pluviometro interpolado pelo NOAA CPC), e so a conversao para
   * classe e para o CN vigente e tabela. E a parte mais medida da camada de
   * terreno — esconde-la sob o selo do envelope perderia o que ela traz.
   */
  hoje: {
    disponivel: boolean;
    motivo?: string;
    provenance?: Provenance;
    resumo?: {
      version: string;
      ate: string;
      n_municipios: number;
      dias_antecedentes: number;
      meses_crescimento: number[];
      estacao_vigente: string | null;
      por_classe: Record<string, number>;
      chuva_5d_mediana_mm: number | null;
      chuva_30d_mediana_mm: number | null;
    };
    limites?: string[];
    municipios?: {
      cod_mun: number;
      municipio: string;
      ate: string;
      chuva_5d_mm: number;
      chuva_30d_mm: number;
      chuva_90d_mm: number;
      dias_desde_chuva: number | null;
      /** I seco · II media · III encharcado — tabela SCS sobre 5 dias. */
      amc: string;
      estacao: string;
      limiar_amc_iii_mm: number;
      cn2: number | null;
      cn_vigente: number | null;
      delta_cn: number | null;
    }[];
  };

  /** Intersecao dos decis superiores das duas camadas — nao um indice novo. */
  concentracao: {
    criterio: string;
    limiar_cn2?: number;
    n?: number;
    municipios: {
      cod_mun: number;
      municipio: string;
      cn2: number;
      indice_rusle_t_ha_ano: number;
      km2_uso_intensivo_em_declive: number;
      resposta: string | null;
    }[];
  };
}
