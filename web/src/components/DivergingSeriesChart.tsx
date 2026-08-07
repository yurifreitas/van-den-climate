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
} from 'recharts';
import type { SeriesPoint } from '../api/types';
import { FRIO, QUENTE, GIZ, BRUMA, CARTA, GRID, alpha } from '../theme/chartColors';

/**
 * Modulo de GRAFICO — pode importar FRIO/QUENTE (unico lugar permitido).
 * Porta `diverging_timeseries()` de app/charts.py: preenchimento QUENTE
 * acima de zero, FRIO abaixo, linha giz por cima, linha de ancora tracejada
 * em zero.
 */
export function DivergingSeriesChart({ points }: { points: SeriesPoint[] }) {
  const data = points.map((p) => ({
    ts: p.timestamp,
    value: p.value,
    pos: p.value >= 0 ? p.value : 0,
    neg: p.value < 0 ? p.value : 0,
  }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <ComposedChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis
          dataKey="ts"
          tick={{ fill: BRUMA, fontFamily: 'IBM Plex Mono', fontSize: 10 }}
          tickFormatter={(v: string) => v.slice(0, 7)}
          minTickGap={24}
        />
        <YAxis tick={{ fill: BRUMA, fontFamily: 'IBM Plex Mono', fontSize: 10 }} width={36} />
        <ReferenceLine y={0} stroke={BRUMA} strokeDasharray="3 3" />
        <Tooltip
          contentStyle={{ background: CARTA, border: `1px solid ${GRID}`, fontFamily: 'IBM Plex Mono', fontSize: 12 }}
          labelStyle={{ color: BRUMA }}
          itemStyle={{ color: GIZ }}
        />
        <Area type="monotone" dataKey="pos" stroke="none" fill={alpha(QUENTE, 0.33)} isAnimationActive={false} />
        <Area type="monotone" dataKey="neg" stroke="none" fill={alpha(FRIO, 0.33)} isAnimationActive={false} />
        <Line type="monotone" dataKey="value" stroke={GIZ} strokeWidth={1} dot={false} isAnimationActive={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
