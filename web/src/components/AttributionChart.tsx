import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from 'recharts';
import type { AttributionBlock } from '../api/types';
import { GIZ, BRUMA, CARTA, GRID } from '../theme/chartColors';

/**
 * Modulo de GRAFICO. Porta `block_attribution_bars()`: participacao por
 * bloco vs contrafactual "removendo ENSO", pedido explicitamente no brief.
 * Neutro (bruma/carta) porque atribuicao de variancia nao e uma anomalia.
 */
export function AttributionChart({ blocks }: { blocks: AttributionBlock[] }) {
  const data = blocks.map((b) => ({
    label: b.label,
    'atribuicao (todos os blocos)': b.share_full,
    'contrafactual — sem ENSO': b.share_without_enso,
  }));

  return (
    <ResponsiveContainer width="100%" height={80 + blocks.length * 50}>
      <BarChart data={data} layout="vertical" margin={{ top: 8, right: 24, left: 8, bottom: 0 }}>
        <CartesianGrid stroke={GRID} horizontal={false} />
        <XAxis type="number" tickFormatter={(v) => `${Math.round(v * 100)}%`} tick={{ fill: BRUMA, fontSize: 10, fontFamily: 'IBM Plex Mono' }} />
        <YAxis type="category" dataKey="label" width={120} tick={{ fill: GIZ, fontSize: 12 }} />
        <Tooltip
          formatter={(v) => `${(Number(v) * 100).toFixed(1)}%`}
          contentStyle={{ background: CARTA, border: `1px solid ${GRID}`, fontFamily: 'IBM Plex Mono', fontSize: 12 }}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: BRUMA }} />
        <Bar isAnimationActive={false} dataKey="atribuicao (todos os blocos)" fill={BRUMA} />
        <Bar isAnimationActive={false} dataKey="contrafactual — sem ENSO" fill={CARTA} stroke={GIZ} strokeWidth={1} />
      </BarChart>
    </ResponsiveContainer>
  );
}
