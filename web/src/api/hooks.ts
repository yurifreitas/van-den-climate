/**
 * Um hook TanStack Query por endpoint do contrato (§ARQUITETURA do brief).
 * staleTime generoso: o dado sazonal muda mensalmente (regra 1 do contrato,
 * §5) — refetch agressivo so gera carga sem ganho de frescor.
 */
import { useQuery } from '@tanstack/react-query';
import { apiGet } from './client';
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
