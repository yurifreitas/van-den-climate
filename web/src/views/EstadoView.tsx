import { useRuler, useSeries } from '../api/hooks';
import { QueryState } from '../components/QueryState';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { DivergingSeriesChart } from '../components/DivergingSeriesChart';
import { View, Section, Panel, Grid } from '../components/ui';
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
    <View
      title="Estado"
      intro="Em que percentil da distribuicao historica cada modo climatico esta agora, e ha quanto tempo essa fase persiste."
    >
      <Section title="Regua de surpresa — percentil causal, trilha de 12 meses">
        <QueryState isLoading={ruler.isLoading} isError={ruler.isError}>
          <Panel footnote="O mes mais recente fica a direita.">
            <div className="ruler">
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
                  <span
                    className={`ruler-channel__value${c.resolution_warning ? ' ruler-channel__value--warning' : ''}`}
                  >
                    {c.percentile.toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
          </Panel>
        </QueryState>
      </Section>

      <Section
        title="Series com banda divergente"
        note="Preenchimento frio abaixo de zero, quente acima — le-se a fase, nao so o nivel."
      >
        <Grid>
          <Panel title="ONI">
            <QueryState isLoading={oni.isLoading} isError={oni.isError}>
              {oni.data && <DivergingSeriesChart points={oni.data.points} />}
            </QueryState>
          </Panel>
          <Panel title="SAM">
            <QueryState isLoading={sam.isLoading} isError={sam.isError}>
              {sam.data && <DivergingSeriesChart points={sam.data.points} />}
            </QueryState>
          </Panel>
        </Grid>
      </Section>
    </View>
  );
}
