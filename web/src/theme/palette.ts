/**
 * Paleta de dado — sistema completo (substitui a regra "so frio/quente").
 *
 * DESIGN.md §1 foi reescrito: cor continua sendo linguagem de DADO, mas agora
 * com quatro trabalhos distintos, cada um com sua regra:
 *
 *   divergente  — polaridade (anomalia -/+). FRIO/QUENTE, neutro cinza no meio.
 *   sequencial  — magnitude (cobertura, probabilidade). UM matiz, claro→escuro.
 *   categorico  — identidade (bloco de atribuicao, alvo, serie). Ordem FIXA.
 *   estado      — situacao (ok/atencao/falha, nivel de risco). Nunca reusado
 *                 como "serie 4", e sempre acompanhado de rotulo/icone.
 *
 * Todos os conjuntos passaram o validador de paleta contra a superficie
 * escura #151E23 (banda de luminancia, piso de croma, separacao sob CVD,
 * piso de visao normal, contraste >= 3:1). Se mudar um hex, rode de novo:
 *   node scripts/validate_palette.js "<hex,...>" --mode dark --surface "#151E23"
 *
 * O que NAO mudou: texto nunca veste a cor do dado. Rotulo, valor e legenda
 * seguem em giz/bruma; a cor mora na marca ao lado.
 */

// ---- divergente: polaridade -------------------------------------------
export const FRIO = '#2B8FD6'; // anomalia negativa
export const QUENTE = '#C1553A'; // anomalia positiva

// ---- superficies (espelham tokens.css; Recharts/ECharts recebem string) --
export const ABISSAL = '#0F1518';
export const CARTA = '#151E23';
export const CARTA_ALTA = '#1B2429';
export const GIZ = '#D8DEE0';
export const BRUMA = '#8A979E';
export const BRUMA_FRACA = '#5E6B72';
export const GRID = '#1E2A31';
export const LINHA = '#243139';

/**
 * Categorico — identidade. Ordem FIXA: a serie 3 e sempre a cor 3, mesmo que
 * a serie 2 seja filtrada. Nunca cicla: a 7a categoria vira "Outros".
 * Validado: pior par adjacente ΔE 14.3 sob deuteranopia, 17.4 em visao normal.
 */
export const CATEGORICO = [
  '#C1553A', // terracota
  '#16A0A8', // ciano
  '#B8862B', // ambar
  '#8B6FC4', // violeta
  '#2E9468', // verde
  '#2B8FD6', // azul
] as const;

export const CATEGORICO_OUTROS = BRUMA_FRACA;

/**
 * Estado — ok / atencao / falha. Validado (ΔE 10.3 deutan, 15.9 normal).
 * REGRA: nunca sozinho. Sempre com rotulo textual ao lado.
 */
export const ESTADO = {
  ok: '#1E9A87',
  atencao: '#A88C22',
  falha: '#C24356',
} as const;

/**
 * Nivel de risco — ordinal de 4 passos. A codificacao PRIMARIA e o
 * comprimento da barra (magnitude); a cor e reforco. Por isso os quatro
 * passos podem ser semanticos sem violar o piso de separacao: nenhum par
 * carrega informacao sozinho.
 */
export const NIVEL = {
  low: '#1E9A87',
  moderate: '#A88C22',
  elevated: '#C4772E',
  high: '#C24356',
} as const;

export const NIVEL_FRACAO: Record<keyof typeof NIVEL, number> = {
  low: 0.25,
  moderate: 0.5,
  elevated: 0.75,
  high: 1,
};

export const NIVEL_LABEL: Record<keyof typeof NIVEL, string> = {
  low: 'BAIXO',
  moderate: 'MODERADO',
  elevated: 'ELEVADO',
  high: 'ALTO',
};

/** Hex -> rgba(), para bandas, areas e lavagens. */
export function alpha(hex: string, a: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${a})`;
}

function mixHex(from: string, to: string, t: number): string {
  const ch = (h: string, i: number) => parseInt(h.slice(1 + i * 2, 3 + i * 2), 16);
  const out = [0, 1, 2].map((i) => Math.round(ch(from, i) + (ch(to, i) - ch(from, i)) * t));
  return `#${out.map((v) => Math.max(0, Math.min(255, v)).toString(16).padStart(2, '0')).join('')}`.toUpperCase();
}

/**
 * Sequencial — magnitude em [0,1]. UM matiz, escuro→claro sobre fundo escuro
 * (a rampa cresce em luminancia, que e o canal que sobrevive a qualquer CVD).
 * Usado em cobertura, probabilidade e contagem.
 */
export function sequencial(t: number, hue: string = FRIO): string {
  const x = Math.max(0, Math.min(1, t));
  // piso: um passo acima da superficie, para que zero ainda seja celula visivel
  return mixHex(GRID, hue, 0.12 + 0.88 * x);
}

/** Rampa sequencial discreta de n passos — para legenda em degraus. */
export function rampaSequencial(n: number, hue: string = FRIO): string[] {
  return Array.from({ length: n }, (_, i) => sequencial(n === 1 ? 1 : i / (n - 1), hue));
}

/**
 * Divergente centrada em 0.5. Meio SEM matiz (cinza neutro) — o ponto morto
 * da escala nao pode parecer uma categoria.
 */
export function diverging(pct: number): string {
  const t = Math.max(0, Math.min(1, pct));
  const base = t < 0.5 ? FRIO : QUENTE;
  const a = Math.abs(t - 0.5) * 2.0;
  return mixHex(CARTA_ALTA, base, 0.25 + 0.75 * a);
}

/** Divergente por valor bruto com dominio simetrico (ex.: ONI em ±3). */
export function divergingValue(v: number, max: number): string {
  return diverging(0.5 + Math.max(-1, Math.min(1, v / max)) / 2);
}

/** Cor categorica por indice, com dobra explicita em "Outros". */
export function categorico(i: number): string {
  return i < CATEGORICO.length ? CATEGORICO[i] : CATEGORICO_OUTROS;
}
