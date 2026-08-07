import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid, ErrorBar } from 'recharts';
import type { TercileSet } from '../api/types';
import { GIZ, BRUMA, GRID } from '../theme/chartColors';
import { TOOLTIP_STYLE, LEGEND_STYLE, AXIS_TICK, fmtOrDash } from './charts/ChartTooltip';

/**
 * Modulo de GRAFICO. Porta `tercile_diagram()` — climatologia SEMPRE ao
 * lado da previsao, nunca sozinha (regra do contrato/brief), com barra de
 * erro na previsao quando `forecast_se` existir.
 *
 * Nao usa FRIO/QUENTE: tercil nao e uma anomalia de sinal (nao ha
 * "abaixo=frio"), entao a distincao aqui e climatologia (contorno, vazado)
 * vs previsao (solido), com gap de 2px entre as duas barras do mesmo grupo
 * (via `barGap`) — nunca contorno como separador.
 */
export function TercileChart({
  climatology,
  forecast,
  forecastSe,
}: {
  climatology: TercileSet;
  forecast: TercileSet;
  forecastSe?: number;
}) {
  const data = [
    { tercil: 'Abaixo', climatologia: climatology.below, previsao: forecast.below, err: forecastSe },
    { tercil: 'Perto da norma', climatologia: climatology.normal, previsao: forecast.normal, err: forecastSe },
    { tercil: 'Acima', climatologia: climatology.above, previsao: forecast.above, err: forecastSe },
  ];

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }} barGap={2} barCategoryGap="30%">
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="tercil" tick={{ ...AXIS_TICK, fontSize: 11 }} />
        <YAxis
          tick={AXIS_TICK}
          width={36}
          domain={[0, 'dataMax']}
          tickFormatter={(v: number) => fmtOrDash(v, (n) => `${Math.round(n * 100)}%`)}
        />
        <Tooltip {...TOOLTIP_STYLE} formatter={(v) => fmtOrDash(v === undefined ? null : Number(v), (n) => `${(n * 100).toFixed(1)}%`)} />
        <Legend {...LEGEND_STYLE} />
        <Bar
          isAnimationActive={false}
          dataKey="climatologia"
          name="climatologia (1951-1990)"
          fill="transparent"
          stroke={BRUMA}
          strokeWidth={1.5}
          maxBarSize={24}
          radius={[4, 4, 0, 0]}
        />
        <Bar
          isAnimationActive={false}
          dataKey="previsao"
          name="previsao vigente"
          fill={GIZ}
          maxBarSize={24}
          radius={[4, 4, 0, 0]}
        >
          {forecastSe !== undefined && <ErrorBar dataKey="err" stroke={BRUMA} strokeWidth={2} width={4} />}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
