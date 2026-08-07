import { useState } from 'react';
import { useForecastAnalogs, useForecastAttribution } from '../api/hooks';
import { QueryState } from '../components/QueryState';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { AttributionChart } from '../components/AttributionChart';
import './views.css';

const SEASONS = ['OND2026', 'JFM2027'];

/**
 * Rota `/evidencia` — pergunta: "o que sustenta esta previsao? Quanto
 * some se removermos ENSO, e quais anos historicos mais se parecem com
 * agora?"
 */
export function EvidenciaView() {
  const [season, setSeason] = useState(SEASONS[0]);
  const attribution = useForecastAttribution(season);
  const analogs = useForecastAnalogs(season);

  return (
    <section>
      <div className="section-title-row">
        <h2>Evidencia — atribuicao e analogos</h2>
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

      <div className="panel">
        <div className="section-title-row">
          <h3>Atribuicao por bloco</h3>
          {attribution.data && <ProvenanceBadge basis={attribution.data.provenance.basis} />}
        </div>
        <QueryState isLoading={attribution.isLoading} isError={attribution.isError}>
          {attribution.data && <AttributionChart blocks={attribution.data.shares} />}
        </QueryState>
      </div>

      <div className="panel">
        <div className="section-title-row">
          <h3>Anos analogos</h3>
          {analogs.data && <ProvenanceBadge basis={analogs.data.provenance.basis} />}
        </div>
        <QueryState isLoading={analogs.isLoading} isError={analogs.isError}>
          <div className="scroll-x">
            <table className="data-table">
              <thead>
                <tr>
                  <th>ano</th>
                  <th>similaridade</th>
                  <th>tercil observado</th>
                </tr>
              </thead>
              <tbody>
                {analogs.data?.analogs.map((a) => (
                  <tr key={a.year}>
                    <td className="num">{a.year}</td>
                    <td className="num">{a.similarity.toFixed(2)}</td>
                    <td className="num">{['Abaixo', 'Perto', 'Acima'][a.observed_tercile]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </QueryState>
      </div>
    </section>
  );
}
