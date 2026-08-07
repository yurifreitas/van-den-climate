import { useState } from 'react';
import { useForecast } from '../api/hooks';
import { QueryState } from '../components/QueryState';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { TercileChart } from '../components/TercileChart';
import { View, Panel, Grid, Metric, Field } from '../components/ui';
import './views.css';

const SEASONS = ['OND2026', 'JFM2027'];

/**
 * Rota `/previsao` — pergunta: "o que a previsao sazonal desloca em relacao
 * a climatologia, e essa previsao passou no criterio de aceitacao?"
 *
 * REGRA do brief: `status: "not_accepted"` e um RESULTADO explicito, nao
 * erro/estado vazio — renderizado como painel de veredito (borda tracejada),
 * e os alvos continuam aparecendo (com a previsao igual/proxima da
 * climatologia).
 */
export function PrevisaoView() {
  const [season, setSeason] = useState(SEASONS[0]);
  const { data, isLoading, isError } = useForecast(season);

  return (
    <View
      title="Previsao"
      intro="O que a previsao sazonal desloca em relacao a climatologia, e se passou no criterio de aceitacao."
      actions={
        <Field label="temporada:">
          <select value={season} onChange={(e) => setSeason(e.target.value)}>
            {SEASONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </Field>
      }
    >
      <QueryState isLoading={isLoading} isError={isError}>
        {data && (
          <>
            <Panel tone="verdict" pad="tight" footnote={data.acceptance.verdict}>
              <Metric
                value={data.acceptance.rpss.point}
                label={`RPSS · IC90 [${data.acceptance.rpss.lo ?? '—'}, ${data.acceptance.rpss.hi ?? '—'}]`}
              />
              <p className="t-data">
                {data.status === 'not_accepted'
                  ? 'RESULTADO: a climatologia permanece vigente.'
                  : `RESULTADO: previsao aceita para ${data.season}.`}
              </p>
              <p className="t-note">criterio: {data.acceptance.criterion}</p>
            </Panel>

            <Grid>
              {data.targets.map((t) => (
                <Panel
                  key={t.id}
                  title={t.label}
                  actions={<ProvenanceBadge basis={t.provenance.basis} />}
                >
                  <TercileChart
                    climatology={t.climatology}
                    forecast={t.terciles}
                    forecastSe={t.forecast_se}
                  />
                </Panel>
              ))}
            </Grid>
          </>
        )}
      </QueryState>
    </View>
  );
}
