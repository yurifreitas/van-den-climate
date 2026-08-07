import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from 'recharts';
import type { AttributionBlock } from '../api/types';
import { GIZ, BRUMA, GRID } from '../theme/chartColors';
import { TOOLTIP_STYLE, LEGEND_STYLE, fmtOrDash } from './charts/ChartTooltip';

/**
 * Modulo de GRAFICO. Porta `block_attribution_bars()`: participacao por
 * bloco vs contrafactual "removendo ENSO", pedido explicitamente no brief.
 * Neutro (bruma/giz) porque atribuicao de variancia nao e uma anomalia.
 *
 * Defeito corrigido: dominio do eixo X ia a 400% quando as participacoes
 * eram 0 (Recharts com `dataMax` sobre valores todos-zero produz um
 * dominio degenerado). Agora o dominio e honesto: [0, 1] (0-100%) sempre
 * que houver algum valor > 0; se tudo for zero, mostra mensagem em vez de
 * grafico vazio/quebrado.
 */
export function AttributionChart({ blocks }: { blocks: AttributionBlock[] }) {
  const allZero = blocks.length === 0 || blocks.every((b) => !b.share_full && !b.share_without_enso);

  if (allZero) {
    return (
      <div
        style={{
          border: `1px solid ${GRID}`,
          borderRadius: 2,
          padding: '24px 16px',
          textAlign: 'center',
          color: BRUMA,
          fontSize: 13,
        }}
      >
        Sem participacao atribuivel a nenhum bloco nesta emissao. Nao ha o que plotar — o dado
        chegou zerado, nao e falha de renderizacao.
      </div>
    );
  }

  const data = blocks.map((b) => ({
    label: b.label,
    'atribuicao (todos os blocos)': b.share_full,
    'contrafactual — sem ENSO': b.share_without_enso,
  }));

  return (
    <ResponsiveContainer width="100%" height={80 + blocks.length * 50}>
      <BarChart data={data} layout="vertical" margin={{ top: 8, right: 24, left: 8, bottom: 0 }} barGap={2}>
        <CartesianGrid stroke={GRID} horizontal={false} />
        <XAxis
          type="number"
          domain={[0, 1]}
          tickFormatter={(v: number) => fmtOrDash(v, (n) => `${Math.round(n * 100)}%`)}
          tick={{ fill: BRUMA, fontSize: 10, fontFamily: 'IBM Plex Mono, monospace' }}
        />
        <YAxis type="category" dataKey="label" width={120} tick={{ fill: GIZ, fontSize: 12 }} />
        <Tooltip {...TOOLTIP_STYLE} formatter={(v) => fmtOrDash(v === undefined ? null : Number(v), (n) => `${(n * 100).toFixed(1)}%`)} />
        <Legend {...LEGEND_STYLE} />
        <Bar
          isAnimationActive={false}
          dataKey="atribuicao (todos os blocos)"
          fill={GIZ}
          maxBarSize={24}
          radius={[0, 4, 4, 0]}
        />
        <Bar
          isAnimationActive={false}
          dataKey="contrafactual — sem ENSO"
          fill="transparent"
          stroke={BRUMA}
          strokeWidth={1.5}
          maxBarSize={24}
          radius={[0, 4, 4, 0]}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
