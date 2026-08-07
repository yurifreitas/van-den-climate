import { useState } from 'react';
import { useForecast } from '../api/hooks';
import { QueryState } from '../components/QueryState';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { TercileChart } from '../components/TercileChart';
import './views.css';

const SEASONS = ['OND2026', 'JFM2027'];

/**
 * Rota `/previsao` — pergunta: "o que a previsao sazonal desloca em relacao
 * a climatologia, e essa previsao passou no criterio de aceitacao?"
 *
 * REGRA do brief: `status: "not_accepted"` e um RESULTADO explicito, nao
 * erro/estado vazio — renderizado como banner de veredito, e os alvos
 * continuam aparecendo (com a previsao igual/proxima da climatologia).
 */
export function PrevisaoView() {
  const [season, setSeason] = useState(SEASONS[0]);
  const { data, isLoading, isError } = useForecast(season);

  return (
    <section>
      <div className="section-title-row">
        <h2>Previsao — trio de alvos</h2>
        <label className="muted">
          temporada:{' '}
          <select value={season} onChange={(e) => setSeason(e.target.value)}>
            {SEASONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
      </div>

      <QueryState isLoading={isLoading} isError={isError}>
        {data && (
          <>
            <div className="acceptance-banner">
              <p className="acceptance-banner__verdict">
                {data.status === 'not_accepted'
                  ? 'RESULTADO: a climatologia permanece vigente.'
                  : `RESULTADO: previsao aceita para ${data.season}.`}
              </p>
              <p className="muted">
                criterio: {data.acceptance.criterion} · RPSS ={' '}
                {data.acceptance.rpss.point ?? '—'} (IC90{' '}
                [{data.acceptance.rpss.lo ?? '—'}, {data.acceptance.rpss.hi ?? '—'}])
              </p>
              <p className="muted">{data.acceptance.verdict}</p>
            </div>

            <div className="card-grid">
              {data.targets.map((t) => (
                <div className="panel" key={t.id}>
                  <div className="section-title-row">
                    <h4>{t.label}</h4>
                    <ProvenanceBadge basis={t.provenance.basis} />
                  </div>
                  <TercileChart climatology={t.climatology} forecast={t.terciles} forecastSe={t.forecast_se} />
                </div>
              ))}
            </div>
          </>
        )}
      </QueryState>
    </section>
  );
}
