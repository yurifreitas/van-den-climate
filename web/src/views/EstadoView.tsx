import { useMemo } from 'react';
import type { CSSProperties } from 'react';
import { useRuler, useSeries } from '../api/hooks';
import type { StateBlock } from '../api/types';
import { QueryState } from '../components/QueryState';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { DivergingSeriesChart } from '../components/DivergingSeriesChart';
import { View, Section, Panel, Grid, Row, Stack } from '../components/ui';
import { diverging } from '../theme/palette';
import './views.css';
import './EstadoView.css';

/**
 * Rota `/estado`.
 *
 * A regua de surpresa ja existia e ja estava certa; o que faltava era ela
 * poder ser LIDA. A versao anterior mostrava doze celulas coloridas sem eixo
 * de tempo, sem legenda de escala e com um numero solto a direita — de modo
 * que "SOI em 0,011" (primeiro percentil da serie inteira, um extremo) tinha
 * exatamente o mesmo peso visual de "SAM em 0,60" (banal).
 *
 * Tres acrescimos, todos sobre o mesmo dado:
 *   1. eixo de meses sob a trilha, para que a leitura tenha direcao;
 *   2. legenda da escala, dizendo que 0 e minimo historico e 1 e maximo;
 *   3. destaque textual do que e extremo — percentil <= 0,10 ou >= 0,90 ganha
 *      uma leitura em palavras, porque numero sozinho nao classifica.
 */

const EXTREMO_ALTO = 0.9;
const EXTREMO_BAIXO = 0.1;

/** Rotulo dos ultimos 12 meses terminando no mes de referencia. */
function meses(asOf: string, n: number): string[] {
  const base = new Date(`${asOf}T00:00:00Z`);
  const nomes = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
  return Array.from({ length: n }, (_, i) => {
    const d = new Date(Date.UTC(base.getUTCFullYear(), base.getUTCMonth() - (n - 1 - i), 1));
    return nomes[d.getUTCMonth()];
  });
}

/**
 * Percentil como texto. Casa decimal SO nos extremos.
 *
 * Sem isso, 0,9967 vira "100º percentil", que se le como "o maior valor ja
 * medido" — afirmacao mais forte que o dado sustenta, e justamente no canal
 * onde a diferenca importa. Nos valores centrais a casa decimal seria ruido.
 */
function pct(p: number): string {
  const extremo = p >= 0.995 || p <= 0.005;
  return `${(p * 100).toFixed(extremo ? 1 : 0)}º`;
}

function leitura(c: StateBlock): { texto: string; tom: 'alto' | 'baixo' | 'normal' } {
  const p = c.percentile;
  if (p >= EXTREMO_ALTO) {
    return {
      texto: `no ${pct(p)} percentil da serie — entre os valores mais altos ja medidos`,
      tom: 'alto',
    };
  }
  if (p <= EXTREMO_BAIXO) {
    return {
      texto: `no ${pct(p)} percentil da serie — entre os valores mais baixos ja medidos`,
      tom: 'baixo',
    };
  }
  return { texto: `no ${pct(p)} percentil da serie — dentro da faixa comum`, tom: 'normal' };
}

export function EstadoView() {
  const ruler = useRuler();
  const oni = useSeries('oni');
  const sam = useSeries('sam');
  const soi = useSeries('soi');

  const canais = useMemo(() => ruler.data?.channels ?? [], [ruler.data]);
  const extremos = useMemo(
    () => canais.filter((c) => c.percentile >= EXTREMO_ALTO || c.percentile <= EXTREMO_BAIXO),
    [canais],
  );

  return (
    <View
      title="Estado"
      intro="Em que percentil da distribuicao historica cada modo climatico esta agora, e ha quanto tempo essa fase persiste."
    >
      {/* Leitura em prosa antes da grade: quem abre a tela precisa saber o que
          esta acontecendo antes de decodificar doze celulas de cor. */}
      {extremos.length > 0 && (
        <div className="leitura-estado">
          <p className="t-body">
            <strong>{extremos.length}</strong>{' '}
            {extremos.length === 1 ? 'canal esta' : 'canais estao'} em territorio extremo:{' '}
            {extremos.map((c, i) => (
              <span key={c.signal_id}>
                {i > 0 && ', '}
                <strong>{c.label}</strong> {leitura(c).texto}
              </span>
            ))}
            .
          </p>
          <p className="t-note">
            Percentil causal: posicao contra tudo o que veio antes, nunca contra o futuro. Extremo
            aqui e descricao do estado, nao previsao de consequencia.
          </p>
        </div>
      )}

      <Section
        title="Regua de surpresa — percentil causal, trilha de 12 meses"
        note="Uma linha por modo climatico. A cor e a escala divergente do dado; o numero a direita e o percentil do mes mais recente."
      >
        <QueryState isLoading={ruler.isLoading} isError={ruler.isError}>
          {ruler.data && (
            <Panel>
              <div className="ruler">
                {canais.map((c) => {
                  const trilha = (c.trail_12m.length ? c.trail_12m : [c.percentile]).slice(-12);
                  const l = leitura(c);
                  return (
                    <div className="ruler-channel" key={c.signal_id}>
                      <span className="ruler-channel__label">
                        {c.label} <ProvenanceBadge basis={c.provenance.basis} />
                      </span>
                      <div className="ruler-channel__track">
                        {trilha.map((v, i) => (
                          <div
                            key={i}
                            className="ruler-channel__cell"
                            style={{ background: diverging(v) }}
                            title={`percentil ${v.toFixed(2)}`}
                          />
                        ))}
                      </div>
                      <span
                        className={`ruler-channel__value${c.resolution_warning ? ' ruler-channel__value--warning' : ''}`}
                        data-tom={l.tom}
                      >
                        {c.percentile.toFixed(2)}
                      </span>
                    </div>
                  );
                })}

                {/* Eixo de tempo: sem ele as doze celulas nao tem direcao, e a
                    trilha vira ornamento. */}
                <div className="ruler-axis">
                  <span />
                  <div className="ruler-axis__meses">
                    {meses(ruler.data.as_of, 12).map((m, i) => (
                      <span key={i}>{m}</span>
                    ))}
                  </div>
                  <span />
                </div>
              </div>

              <Row>
                <span className="escala-legenda t-note">
                  <span className="escala-legenda__rampa" />
                  0 = minimo da serie · 0,5 = mediana · 1 = maximo
                </span>
                <span className="t-note">
                  ultimos 12 meses, mais recente a direita · referencia {ruler.data.as_of}
                </span>
              </Row>
            </Panel>
          )}
        </QueryState>
      </Section>

      <Section
        title="Valor corrente e trilha, por modo"
        note="O percentil diz a posicao; o valor diz a magnitude. Os dois juntos evitam ler 'alto na serie' como 'alto em absoluto'."
      >
        <Grid min={240}>
          {canais.map((c) => {
            const l = leitura(c);
            return (
              <Panel key={c.signal_id} title={c.label}>
                <Stack gap={2}>
                  <Row>
                    <span className="t-hero" data-tom={l.tom}>
                      {c.value_current === null || c.value_current === undefined
                        ? '—'
                        : c.value_current.toFixed(2)}
                    </span>
                    <span
                      className="percentil-chip t-data"
                      style={{ '--chip-cor': diverging(c.percentile) } as CSSProperties}
                    >
                      p{pct(c.percentile).replace('º', '')}
                    </span>
                  </Row>
                  <p className="t-small">{l.texto}</p>
                  {c.resolution_warning && (
                    <p className="t-note">
                      Resolucao grossa: t &lt; 30, o percentil so pode assumir poucos valores
                      discretos.
                    </p>
                  )}
                  <ProvenanceBadge basis={c.provenance.basis} />
                </Stack>
              </Panel>
            );
          })}
        </Grid>
      </Section>

      <Section
        title="Series com banda divergente"
        note="Preenchimento frio abaixo de zero, quente acima — le-se a fase, nao so o nivel."
      >
        <Grid min={380}>
          <Panel title="ONI — estado ENSO">
            <QueryState isLoading={oni.isLoading} isError={oni.isError}>
              {oni.data && <DivergingSeriesChart points={oni.data.points} />}
            </QueryState>
          </Panel>
          <Panel
            title="SOI — oscilacao sul (atmosfera)"
            footnote="Contraparte atmosferica do ENSO: SOI negativo acompanha El Nino. Por isso a banda aparece espelhada em relacao ao ONI — sao o mesmo fenomeno visto de dois lados."
          >
            <QueryState isLoading={soi.isLoading} isError={soi.isError}>
              {soi.data && <DivergingSeriesChart points={soi.data.points} />}
            </QueryState>
          </Panel>
          <Panel title="SAM — modo anular sul">
            <QueryState isLoading={sam.isLoading} isError={sam.isError}>
              {sam.data && <DivergingSeriesChart points={sam.data.points} />}
            </QueryState>
          </Panel>
          {/* Nino 3.4 NAO entra aqui. A serie do contrato e TSM ABSOLUTA
              (24-29 °C), e uma banda divergente em torno de zero a renderizaria
              inteiramente "quente" — um grafico tecnicamente correto e
              completamente enganoso. O ONI acima ja e a anomalia dessa mesma
              caixa, que e a leitura que este painel quer. */}
        </Grid>
      </Section>
    </View>
  );
}
