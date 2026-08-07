import { useRuler, useSeries } from '../api/hooks';
import { QueryState } from '../components/QueryState';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { DivergingSeriesChart } from '../components/DivergingSeriesChart';
import { diverging } from '../theme/chartColors';
import './views.css';

/**
 * Rota `/estado` — pergunta: "em que percentil da distribuicao historica
 * cada modo climatico esta agora, e ha quanto tempo essa fase persiste?"
 *
 * Regua de Surpresa: console de mixagem (metafora do brief) — um canal
 * vertical por variavel, trilha de 12 meses, escala divergente UNICA entre
 * canais para permitir comparar ENSO/SAM/Atlantico num so golpe de vista.
 */
export function EstadoView() {
  const ruler = useRuler();
  const oni = useSeries('oni');
  const sam = useSeries('sam');

  return (
    <section>
      <h2>Estado — Regua de Surpresa</h2>
      <p className="muted">
        Percentil causal (resolucao 1/t) por canal, trilha dos ultimos 12 meses. O mes
        mais recente fica a direita.
      </p>
      <QueryState isLoading={ruler.isLoading} isError={ruler.isError}>
        <div className="ruler panel">
          {ruler.data?.channels.map((c) => (
            <div className="ruler-channel" key={c.signal_id}>
              <span className="ruler-channel__label">
                {c.label} <ProvenanceBadge basis={c.provenance.basis} />
              </span>
              <div className="ruler-channel__track">
                {(c.trail_12m.length ? c.trail_12m : [c.percentile]).slice(-12).map((v, i) => (
                  <div
                    key={i}
                    className="ruler-channel__cell"
                    style={{ background: diverging(v) }}
                    title={`percentil=${v.toFixed(2)}`}
                  />
                ))}
              </div>
              <span className={`ruler-channel__value${c.resolution_warning ? ' ruler-channel__value--warning' : ''}`}>
                {c.percentile.toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      </QueryState>

      <h3>Series com banda divergente</h3>
      <p className="muted">Preenchimento frio abaixo de zero, quente acima — le-se a fase, nao so o nivel.</p>
      <div className="card-grid">
        <div className="panel">
          <h4>ONI</h4>
          <QueryState isLoading={oni.isLoading} isError={oni.isError}>
            {oni.data && <DivergingSeriesChart points={oni.data.points} />}
          </QueryState>
        </div>
        <div className="panel">
          <h4>SAM</h4>
          <QueryState isLoading={sam.isLoading} isError={sam.isError}>
            {sam.data && <DivergingSeriesChart points={sam.data.points} />}
          </QueryState>
        </div>
      </div>
    </section>
  );
}
