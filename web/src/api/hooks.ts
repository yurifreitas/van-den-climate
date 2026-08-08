/**
 * Um hook TanStack Query por endpoint do contrato (§ARQUITETURA do brief).
 * staleTime generoso: o dado sazonal muda mensalmente (regra 1 do contrato,
 * §5) — refetch agressivo so gera carga sem ganho de frescor.
 */
import { useQuery } from '@tanstack/react-query';
import { apiGet } from './client';
import type {
  AguasMeta,
  AnalogsResponse,
  Cenario,
  CruzamentoAguas,
  DossieResponse,
  HistoricoResponse,
  OutlookResponse,
  PessoalResponse,
  PlanoResponse,
  RecursosResponse,
  RespostaResponse,
  AttributionResponse,
  BreaksResponse,
  CoverageResponse,
  ForecastResponse,
  LedgerResponse,
  LedgerSkillResponse,
  MalhaResponse,
  MetaResponse,
  MunicipalRiskResponse,
  ReferencesResponse,
  RiskResponse,
  RulerResponse,
  SeriesResponse,
  SignalId,
  SourcesResponse,
  StateResponse,
} from './types';

const STALE = 5 * 60 * 1000; // 5 min — coerente com "muda mensalmente, nao a cada request"

export function useMeta() {
  return useQuery({ queryKey: ['meta'], queryFn: () => apiGet<MetaResponse>('/meta'), staleTime: STALE });
}

export function useAppState() {
  return useQuery({ queryKey: ['state'], queryFn: () => apiGet<StateResponse>('/state'), staleTime: STALE });
}

export function useRuler() {
  return useQuery({ queryKey: ['state', 'ruler'], queryFn: () => apiGet<RulerResponse>('/state/ruler'), staleTime: STALE });
}

export function useSeries(signal: SignalId, from?: string, to?: string) {
  return useQuery({
    queryKey: ['series', signal, from, to],
    queryFn: () => apiGet<SeriesResponse>(`/series/${signal}`, { from, to }),
    staleTime: STALE,
  });
}

export function useForecast(season: string) {
  return useQuery({
    queryKey: ['forecast', season],
    queryFn: () => apiGet<ForecastResponse>(`/forecast/${season}`),
    staleTime: STALE,
  });
}

export function useForecastAttribution(season: string) {
  return useQuery({
    queryKey: ['forecast', season, 'attribution'],
    queryFn: () => apiGet<AttributionResponse>(`/forecast/${season}/attribution`),
    staleTime: STALE,
  });
}

export function useForecastAnalogs(season: string) {
  return useQuery({
    queryKey: ['forecast', season, 'analogs'],
    queryFn: () => apiGet<AnalogsResponse>(`/forecast/${season}/analogs`),
    staleTime: STALE,
  });
}

export function useRiskCurrent() {
  return useQuery({ queryKey: ['risk', 'current'], queryFn: () => apiGet<RiskResponse>('/risk/current'), staleTime: STALE });
}

/**
 * Catalogo COMPLETO de perigos — inclui os que nao tem nivel a declarar.
 *
 * A tela de risco precisa deste, nao de `/risk/current`: `current` filtra
 * para o que esta ativo, e com isso remove `flash_flood` (level: null), que
 * e justamente o item que a central de risco tem obrigacao de mostrar. Um
 * horizonte sem camada construida tem que aparecer declarado; some-lo faz a
 * central parecer completa e alguem assume cobertura que nao existe.
 */
export function useHazardsCatalog() {
  return useQuery({ queryKey: ['risk', 'hazards'], queryFn: () => apiGet<RiskResponse>('/risk/hazards'), staleTime: STALE });
}

export function useLedger(target?: string, from?: string, to?: string) {
  return useQuery({
    queryKey: ['ledger', target, from, to],
    queryFn: () => apiGet<LedgerResponse>('/ledger', { target, from, to }),
    staleTime: STALE,
  });
}

export function useLedgerSkill() {
  return useQuery({
    queryKey: ['ledger', 'skill'],
    queryFn: () => apiGet<LedgerSkillResponse>('/ledger/skill'),
    staleTime: STALE,
  });
}

export function useHealthCoverage() {
  return useQuery({
    queryKey: ['health', 'coverage'],
    queryFn: () => apiGet<CoverageResponse>('/health/coverage'),
    staleTime: STALE,
  });
}

export function useHealthBreaks() {
  return useQuery({
    queryKey: ['health', 'breaks'],
    queryFn: () => apiGet<BreaksResponse>('/health/breaks'),
    staleTime: STALE,
  });
}

export function useHealthSources() {
  return useQuery({
    queryKey: ['health', 'sources'],
    queryFn: () => apiGet<SourcesResponse>('/health/sources'),
    staleTime: STALE,
  });
}

export function useReferences() {
  return useQuery({
    queryKey: ['references'],
    queryFn: () => apiGet<ReferencesResponse>('/references'),
    staleTime: STALE,
  });
}

/**
 * Risco municipal (497 linhas, ~600 KB). Sem paginacao de proposito: o mapa
 * precisa dos 497 de uma vez para colorir, e paginar obrigaria o front a
 * remontar a colecao inteira antes de desenhar qualquer coisa.
 */
export function useMunicipalRisk(cenario: Cenario = 'atual') {
  return useQuery({
    queryKey: ['risk', 'municipal', cenario],
    queryFn: () => apiGet<MunicipalRiskResponse>('/risk/municipal', { cenario }),
    staleTime: STALE,
    // Troca de cenario mantem a tabela anterior na tela enquanto a nova chega:
    // sem isso o mapa inteiro pisca para o esqueleto a cada clique, e a
    // comparacao entre horizontes — que e o ponto do seletor — se perde.
    placeholderData: (anterior) => anterior,
  });
}

/** Dossie municipal: as dez camadas reunidas na ordem da decisao. */
export function useDossie(codMun: number | null, cenario: Cenario = 'atual') {
  return useQuery({
    queryKey: ['dossie', codMun, cenario],
    queryFn: () => apiGet<DossieResponse>(`/dossie/${codMun}`, { cenario }),
    enabled: codMun !== null,
    staleTime: STALE,
  });
}

/** Quadro de pessoal, voluntariado instalado e pares de auxilio mutuo. */
export function usePessoal() {
  return useQuery({
    queryKey: ['pessoal'],
    queryFn: () => apiGet<PessoalResponse>('/pessoal'),
    staleTime: STALE,
  });
}

/**
 * Mapa geral de recursos e vazios de cobertura. `staleTime` alto: cadastro
 * de estabelecimento e mapeamento OSM nao mudam em escala de minutos.
 */
export function useRecursos() {
  return useQuery({
    queryKey: ['recursos'],
    queryFn: () => apiGet<RecursosResponse>('/recursos'),
    staleTime: Infinity,
    gcTime: Infinity,
  });
}

/** Plano de acao preventiva: de lacuna declarada para acao nomeada. */
export function usePlano(cenario: Cenario = 'atual') {
  return useQuery({
    queryKey: ['plano', cenario],
    queryFn: () => apiGet<PlanoResponse>('/plano', { cenario }),
    staleTime: STALE,
    placeholderData: (anterior) => anterior,
  });
}

/**
 * Historia longa da chuva de primavera e o deslocamento por ENSO.
 * `staleTime: Infinity` — a serie do GHCN termina em 1999 e nao muda.
 */
export function useHistorico() {
  return useQuery({
    queryKey: ['historico', 'chuva'],
    queryFn: () => apiGet<HistoricoResponse>('/historico/chuva'),
    staleTime: Infinity,
    gcTime: Infinity,
  });
}

/**
 * Vulnerabilidade, capacidade de saude, autonomia logistica e resposta.
 * Dominio do DEPOIS do evento — separado do indice de prioridade de propósito.
 */
export function useResposta() {
  return useQuery({
    queryKey: ['resposta', 'municipios'],
    queryFn: () => apiGet<RespostaResponse>('/resposta/municipios'),
    staleTime: STALE,
  });
}

/** Metadados da memoria hidrica (bbox do overlay, totais, limites). */
export function useAguasMeta() {
  return useQuery({
    queryKey: ['geo', 'aguas', 'meta'],
    queryFn: () => apiGet<AguasMeta>('/geo/aguas/meta'),
    staleTime: Infinity,
    gcTime: Infinity,
  });
}

/** Municipios onde a agua voltou: memoria hidrica + inundacao declarada em 2024. */
export function useCruzamentoAguas() {
  return useQuery({
    queryKey: ['risk', 'municipal', 'cruzamento', 'aguas'],
    queryFn: () => apiGet<CruzamentoAguas>('/risk/municipal/cruzamento/aguas', { limit: '30' }),
    staleTime: STALE,
  });
}

/** Boletim ENSO do CPC — a unica camada prospectiva. Contexto, nunca feature. */
export function useEnsoOutlook() {
  return useQuery({
    queryKey: ['outlook', 'enso'],
    queryFn: () => apiGet<OutlookResponse>('/outlook/enso'),
    staleTime: STALE,
  });
}

/**
 * Malha municipal. `staleTime: Infinity` porque geometria de municipio muda
 * por lei estadual, nao por ingestao — refazer o fetch de 256 KB a cada 5 min
 * seria carga pura. Sai do cache so no reload.
 */
export function useMalhaMunicipal() {
  return useQuery({
    queryKey: ['geo', 'municipios'],
    queryFn: () => apiGet<MalhaResponse>('/geo/municipios'),
    staleTime: Infinity,
    gcTime: Infinity,
  });
}
