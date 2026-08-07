/**
 * Modulo ISOLADO para FRIO/QUENTE (§9.2, app/theme.py).
 *
 * Regra critica portada do brief: essas duas cores sao EXCLUSIVAS DO DADO.
 * Nenhum componente de UI (botao, badge, borda, foco, link, estado ativo)
 * pode importar deste arquivo por motivo decorativo — cor aqui significa
 * sempre anomalia negativa/positiva, nunca estilo.
 *
 * O teste `src/theme/__tests__/palette.test.ts` faz grep no restante do
 * codigo-fonte por estes dois hex e falha se aparecerem fora de modulos de
 * grafico (arquivos que importam este modulo ou terminam em Chart.tsx).
 */

export const FRIO = '#3E7FA8'; // anomalia negativa — SOMENTE dado
export const QUENTE = '#C1553A'; // anomalia positiva — SOMENTE dado

// Cores neutras de apoio ao grafico (repetidas aqui, iguais a tokens.css,
// porque Recharts recebe string de cor via prop, nao via CSS var em todo lugar).
export const ABISSAL = '#0F1518';
export const CARTA = '#1B2429';
export const GIZ = '#D8DEE0';
export const BRUMA = '#7C8A90';
export const GRID = '#253036';

/** Hex -> rgba() com transparencia, para bandas/areas divergentes. */
export function alpha(hex: string, a: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${a})`;
}

/**
 * Percentil causal [0,1] -> cor da escala divergente, centrada em 0.5.
 * Espelha `diverging()` de app/theme.py: mistura FRIO/QUENTE com CARTA
 * proporcional a distancia do centro, nunca cor pura em percentis medianos.
 */
export function diverging(pct: number): string {
  const t = Math.max(0, Math.min(1, pct));
  const base = t < 0.5 ? FRIO : QUENTE;
  const a = Math.abs(t - 0.5) * 2.0;
  const mix = (c: number, bc: number) => Math.round(bc + (c - bc) * (0.25 + 0.75 * a));
  const r = mix(parseInt(base.slice(1, 3), 16), parseInt(CARTA.slice(1, 3), 16));
  const g = mix(parseInt(base.slice(3, 5), 16), parseInt(CARTA.slice(3, 5), 16));
  const b = mix(parseInt(base.slice(5, 7), 16), parseInt(CARTA.slice(5, 7), 16));
  return `#${[r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('')}`.toUpperCase();
}
