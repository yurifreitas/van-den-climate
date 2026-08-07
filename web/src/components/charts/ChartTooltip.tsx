import { CARTA, GRID, BRUMA, GIZ } from '../../theme/chartColors';

/**
 * Primitivas comuns de grafico (Recharts) — estilo unico de tooltip/legenda
 * para todos os graficos do app. Texto SEMPRE em giz/bruma, nunca na cor do
 * dado (§1 DESIGN.md). Valor ausente formata como "—", nunca "0".
 */
export const TOOLTIP_STYLE = {
  contentStyle: {
    background: CARTA,
    border: `1px solid ${GRID}`,
    borderRadius: 2,
    fontFamily: 'IBM Plex Mono, monospace',
    fontSize: 12,
    color: GIZ,
  },
  labelStyle: { color: BRUMA, marginBottom: 4 },
  itemStyle: { color: GIZ },
  cursor: { stroke: BRUMA, strokeWidth: 1, strokeDasharray: '0' },
} as const;

export const LEGEND_STYLE = {
  wrapperStyle: { fontSize: 11, color: BRUMA, fontFamily: 'Inter Tight, sans-serif' },
} as const;

export const AXIS_TICK = { fill: BRUMA, fontFamily: 'IBM Plex Mono, monospace', fontSize: 10 };

/** "—" para ausencia, nunca 0. Uso em tickFormatter/tooltip formatter. */
export function fmtOrDash(v: number | null | undefined, fmt: (n: number) => string): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return fmt(v);
}
