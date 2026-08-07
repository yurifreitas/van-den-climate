import type React from 'react';
import { useMemo, useState } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid,
  Label,
} from 'recharts';
import type { SeriesPoint } from '../api/types';
import { FRIO, QUENTE, GIZ, BRUMA, GRID, alpha } from '../theme/chartColors';
import { TOOLTIP_STYLE, AXIS_TICK, fmtOrDash } from './charts/ChartTooltip';

/**
 * Modulo de GRAFICO — pode importar FRIO/QUENTE (unico lugar permitido).
 *
 * Opacidade do preenchimento fixa em 12% (10-14%, §5 DESIGN.md — literal):
 * lavagem, nunca bloco saturado. A linha giz por cima carrega a leitura de
 * magnitude; o preenchimento so sinaliza o sinal (frio/quente) do desvio.
 * Porta `diverging_timeseries()` de app/charts.py: preenchimento QUENTE
 * acima de zero, FRIO abaixo, linha giz por cima, linha de zero explicita.
 *
 * Janela padrao de 20 anos (§5 DESIGN.md) com controle para 20a/50a/completa.
 * Defeito corrigido: na serie completa (~900 pontos mensais) a banda
 * divergente sumia por densidade — agora agrega para media anual sempre que
 * a janela visivel excede ~180 pontos, preservando a leitura da banda.
 */
type Window = '20' | '50' | 'full';

const WINDOW_LABEL: Record<Window, string> = { '20': '20 anos', '50': '50 anos', full: 'completa' };
// Acima disto, agrega por ano. 240 pontos mensais (20 anos) renderizam bem;
// agregar ai escondia o pico corrente — o ONI de 1.39 aparecia como 0.39, em
// contradicao direta com o indicador do cabecalho.
const DENSITY_THRESHOLD = 260;

const controlsRowStyle: React.CSSProperties = {
  display: 'flex',
  flexWrap: 'wrap',
  alignItems: 'center',
  gap: 8,
  marginBottom: 8,
};

const windowBtnStyle: React.CSSProperties = {
  fontFamily: 'IBM Plex Mono, monospace',
  fontSize: 11,
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  color: BRUMA,
  background: 'transparent',
  border: `1px solid ${GRID}`,
  borderRadius: 999,
  padding: '3px 10px',
  cursor: 'pointer',
};

const windowBtnActiveStyle: React.CSSProperties = {
  color: GIZ,
  borderColor: BRUMA,
};

const noteStyle: React.CSSProperties = {
  fontSize: 12,
  color: BRUMA,
};

function yearOf(ts: string): number {
  return Number(ts.slice(0, 4));
}

function aggregateYearly(points: SeriesPoint[]): SeriesPoint[] {
  const byYear = new Map<number, { sum: number; n: number }>();
  for (const p of points) {
    const y = yearOf(p.timestamp);
    const cur = byYear.get(y) ?? { sum: 0, n: 0 };
    cur.sum += p.value;
    cur.n += 1;
    byYear.set(y, cur);
  }
  return Array.from(byYear.entries())
    .sort(([a], [b]) => a - b)
    .map(([y, { sum, n }]) => ({ timestamp: `${y}-01`, value: sum / n }));
}

export function DivergingSeriesChart({ points }: { points: SeriesPoint[] }) {
  const [win, setWin] = useState<Window>('20');

  const windowed = useMemo(() => {
    if (points.length === 0) return points;
    if (win === 'full') return points;
    const lastYear = yearOf(points[points.length - 1].timestamp);
    const years = win === '20' ? 20 : 50;
    return points.filter((p) => yearOf(p.timestamp) > lastYear - years);
  }, [points, win]);

  const dense = windowed.length > DENSITY_THRESHOLD;
  const displayed = useMemo(() => (dense ? aggregateYearly(windowed) : windowed), [windowed, dense]);

  // Dominio SIMETRICO em torno de zero e ajustado ao dado da janela. O
  // automatico do Recharts levava o eixo do ONI a 6.0 com maximo real 1.39 —
  // metade do painel vazia, e a amplitude da anomalia parecendo menor do que e.
  // Simetria importa aqui: numa escala divergente, +1 e -1 precisam ocupar a
  // mesma distancia visual, senao a leitura de fase fica enviesada.
  const yDomain = useMemo<[number, number]>(() => {
    const vals = displayed.map((p) => p.value).filter((v) => Number.isFinite(v));
    if (!vals.length) return [-1, 1];
    const m = Math.max(...vals.map(Math.abs));
    const step = m <= 1 ? 0.5 : m <= 3 ? 1 : 2;
    const top = Math.max(step, Math.ceil(m / step) * step);
    return [-top, top];
  }, [displayed]);

  const data = displayed.map((p, i) => ({
    ts: p.timestamp,
    value: p.value,
    pos: p.value >= 0 ? p.value : 0,
    neg: p.value < 0 ? p.value : 0,
    isLast: i === displayed.length - 1,
  }));

  // Fracao da altura do plot onde cai o zero (0.5 com dominio simetrico).

  const lastPoint = data[data.length - 1];

  return (
    <div>
      <div style={controlsRowStyle} role="group" aria-label="janela de tempo">
        {(['20', '50', 'full'] as Window[]).map((w) => (
          <button
            key={w}
            type="button"
            style={win === w ? { ...windowBtnStyle, ...windowBtnActiveStyle } : windowBtnStyle}
            onClick={() => setWin(w)}
            aria-pressed={win === w}
          >
            {WINDOW_LABEL[w]}
          </button>
        ))}
        {dense && (
          <span style={noteStyle}>
            agregado por media anual ({displayed.length} pontos) — densidade da janela original: {windowed.length} pontos
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={data} margin={{ top: 8, right: 48, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis
            dataKey="ts"
            tick={AXIS_TICK}
            tickFormatter={(v: string) => (dense ? v.slice(0, 4) : v.slice(0, 7))}
            minTickGap={24}
          />
          <YAxis
            tick={AXIS_TICK}
            width={36}
            domain={yDomain}
            tickFormatter={(v: number) => fmtOrDash(v, (n) => n.toFixed(1))}
          />
          <ReferenceLine y={0} stroke={BRUMA} strokeWidth={1}>
            <Label value="0" position="insideLeft" fill={BRUMA} fontSize={10} fontFamily="IBM Plex Mono, monospace" />
          </ReferenceLine>
          <Tooltip
            {...TOOLTIP_STYLE}
            formatter={(v) => fmtOrDash(v === undefined ? null : Number(v), (n) => n.toFixed(2))}
            labelFormatter={(v) => String(v ?? '')}
          />
          {/* Duas Areas ancoradas em zero (`baseValue={0}`), nao um gradiente:
              o gradiente com `objectBoundingBox` mapeia na caixa da PROPRIA
              area, nao no plot, entao a parada do zero cai em lugar errado e
              a banda some.

              Opacidade 0.62, nao os ~10% da regra de "area como lavagem": a
              regra pressupoe que a LINHA carrega a cor da serie. Aqui a linha
              e neutra e o preenchimento e a codificacao inteira — a 12% sobre
              fundo escuro, frio e quente viram o mesmo cinza e o grafico perde
              exatamente o que existe para mostrar. */}
          <Area type="monotone" dataKey="pos" baseValue={0} stroke="none" fill={alpha(QUENTE, 0.62)} isAnimationActive={false} />
          <Area type="monotone" dataKey="neg" baseValue={0} stroke="none" fill={alpha(FRIO, 0.62)} isAnimationActive={false} />
          <Line type="monotone" dataKey="value" stroke={GIZ} strokeOpacity={0.5} strokeWidth={1.25} dot={false} isAnimationActive={false} />
          {lastPoint && (
            <ReferenceLine x={lastPoint.ts} stroke="transparent">
              <Label
                value={fmtOrDash(lastPoint.value, (n) => n.toFixed(2))}
                position="right"
                fill={GIZ}
                fontSize={11}
                fontFamily="IBM Plex Mono, monospace"
              />
            </ReferenceLine>
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
