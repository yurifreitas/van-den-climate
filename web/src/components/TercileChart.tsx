import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid, ErrorBar } from 'recharts';
import type { TercileSet } from '../api/types';
import { GIZ, BRUMA, CARTA, GRID } from '../theme/chartColors';

/**
 * Modulo de GRAFICO. Porta `tercile_diagram()` — climatologia SEMPRE ao
 * lado da previsao, nunca sozinha (regra do contrato/brief), com barra de
 * erro na previsao quando `forecast_se` existir.
 *
 * Nao usa FRIO/QUENTE: tercil nao e uma anomalia de sinal (nao ha
 * "abaixo=frio"), entao a distincao aqui e climatologia (contorno) vs
 * previsao (solido), ambos em tons neutros.
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
    { tercil: 'Abaixo', climatologia: climatology.below, previsao: forecast.below, err: forecastSe ?? 0 },
    { tercil: 'Perto da norma', climatologia: climatology.normal, previsao: forecast.normal, err: forecastSe ?? 0 },
    { tercil: 'Acima', climatologia: climatology.above, previsao: forecast.above, err: forecastSe ?? 0 },
  ];

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="tercil" tick={{ fill: BRUMA, fontFamily: 'IBM Plex Mono', fontSize: 11 }} />
        <YAxis
          tick={{ fill: BRUMA, fontFamily: 'IBM Plex Mono', fontSize: 10 }}
          width={36}
          domain={[0, 'dataMax']}
        />
        <Tooltip
          contentStyle={{ background: CARTA, border: `1px solid ${GRID}`, fontFamily: 'IBM Plex Mono', fontSize: 12 }}
          labelStyle={{ color: BRUMA }}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: BRUMA }} />
        <Bar isAnimationActive={false} dataKey="climatologia" name="climatologia (1951-1990)" fill={CARTA} stroke={BRUMA} strokeWidth={1} />
        <Bar isAnimationActive={false} dataKey="previsao" name="previsao vigente" fill={BRUMA}>
          <ErrorBar dataKey="err" stroke={GIZ} width={4} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
