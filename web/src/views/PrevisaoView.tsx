import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useEnsoOutlook, useForecast, useHistorico } from '../api/hooks';
import { QueryState } from '../components/QueryState';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { TercileChart } from '../components/TercileChart';
import { View, Panel, Grid, Field, Row, Section, Stack } from '../components/ui';
import './views.css';
import './PrevisaoView.css';

const SEASONS = ['OND2026', 'JFM2027'];

const METRICAS_HIST = [
  { id: 'freq_dias_umidos', label: 'dias umidos', unidade: '', casas: 3 },
  { id: 'intensidade_mm', label: 'intensidade', unidade: 'mm/dia', casas: 2 },
  { id: 'p95_mm', label: 'p95 diario', unidade: 'mm', casas: 2 },
  { id: 'total_mm', label: 'total da estacao', unidade: 'mm', casas: 0 },
] as const;

/**
 * Rota `/previsao`.
 *
 * A versao anterior tratava `not_accepted` como um estado quase-vazio: um
 * RPSS "—" solto no topo e tres graficos de barras identicas em 33%. Estava
 * correto e parecia defeito — a informacao mais importante da engine chegava
 * com cara de bug de renderizacao.
 *
 * Esta versao inverte a hierarquia. "Nenhuma previsao aceita" e a MANCHETE,
 * porque e o resultado: a climatologia e a previsao vigente, e a barra plana
 * em 33/33/34 E a previsao, nao a ausencia dela.
 *
 * E, tendo dito isso, a pagina responde a pergunta que naturalmente vem em
 * seguida — "entao nao se sabe nada?" — juntando o que de fato se sabe e que
 * mora em outras duas camadas: o composto historico medido (o que El Nino fez
 * em 50 primaveras) e o outlook oficial do CPC (o que se espera desta). Sao
 * afirmacoes de natureza diferente da previsao aceita, e a tela diz qual e
 * qual.
 */
export function PrevisaoView() {
  const [season, setSeason] = useState(SEASONS[0]);
  const { data, isLoading, isError } = useForecast(season);
  const historico = useHistorico();
  const outlook = useEnsoOutlook();

  const desloc = historico.data?.composto?.deslocamento_elnino_vs_neutro;
  const naoAceita = data?.status === 'not_accepted';

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
            {/* Veredito como manchete. Um resultado negativo com peso
                tipografico de resultado, nao de erro. */}
            <div className="veredito-bloco" data-status={data.status}>
              <p className="veredito-bloco__titulo t-display">
                {naoAceita ? 'Nenhuma previsao aceita' : `Previsao aceita para ${data.season}`}
              </p>
              <p className="veredito-bloco__linha t-body">
                {naoAceita
                  ? 'A climatologia e a previsao vigente para ' + data.season + '.'
                  : 'O modelo passou o criterio de aceitacao.'}
              </p>
              <Row>
                <span className="t-note">
                  criterio: {data.acceptance.criterion} · RPSS{' '}
                  {data.acceptance.rpss.point ?? 'nao calculado'} · IC90 [
                  {data.acceptance.rpss.lo ?? '—'}, {data.acceptance.rpss.hi ?? '—'}]
                </span>
                <ProvenanceBadge basis={naoAceita ? 'measured' : 'modeled'} />
              </Row>
              {naoAceita && (
                <p className="t-note veredito-bloco__nota">
                  RPSS aparece como nao calculado porque nenhum modelo chegou a ser submetido ao
                  criterio — as Camadas 5 e 6 nao foram construidas. &quot;Nao aceito&quot; aqui
                  significa <em>nao ha candidato</em>, nao <em>o candidato falhou</em>.
                </p>
              )}
            </div>

            <Section
              title="A previsao vigente, por alvo"
              note={
                naoAceita
                  ? 'As barras coincidem com a climatologia porque a climatologia E a previsao. Barra plana em 33/33/34 significa "nenhum deslocamento de probabilidade" — e uma afirmacao, nao um grafico vazio.'
                  : undefined
              }
            >
              <Grid>
                {data.targets.map((t) => (
                  <Panel
                    key={t.id}
                    title={t.label}
                    actions={<ProvenanceBadge basis={t.provenance.basis} />}
                    footnote={
                      t.provenance.n_effective
                        ? `climatologia 1951-1990 · n = ${t.provenance.n_effective}`
                        : undefined
                    }
                  >
                    <TercileChart
                      climatology={t.climatology}
                      forecast={t.terciles}
                      forecastSe={t.forecast_se}
                    />
                  </Panel>
                ))}
              </Grid>
            </Section>

            {/* A pergunta que vem depois do "nao aceita". */}
            <Section
              title="Entao o que se sabe?"
              note="Duas afirmacoes de natureza diferente da previsao aceita. Nenhuma delas e previsao desta engine."
            >
              <Grid min={330}>
                <Panel
                  title="O que El Nino fez em 50 primaveras"
                  actions={<ProvenanceBadge basis="measured" />}
                  footnote={
                    <>
                      Composto medido sobre 66 estacoes, 1950-1999. E diferenca de media observada,
                      nao previsao: nao diz o que acontece nesta temporada.{' '}
                      <Link to="/historico">ver a serie completa</Link>.
                    </>
                  }
                >
                  {desloc ? (
                    <ul className="lista-desloc">
                      {METRICAS_HIST.map((m) => {
                        const d = desloc[m.id];
                        if (!d) return null;
                        return (
                          <li key={m.id} data-sep={d.separa_de_zero ? 'sim' : undefined}>
                            <span className="t-small">{m.label}</span>
                            <span className="t-data">
                              {d.delta > 0 ? '+' : ''}
                              {d.delta.toFixed(m.casas)} {m.unidade}
                            </span>
                            <span className="t-note">
                              [{d.ic90[0].toFixed(m.casas)}, {d.ic90[1].toFixed(m.casas)}]
                              {d.separa_de_zero ? '' : ' cruza zero'}
                            </span>
                          </li>
                        );
                      })}
                    </ul>
                  ) : (
                    <p className="t-small">
                      Camada historica nao calculada. Rode a ingestao do GHCN.
                    </p>
                  )}
                </Panel>

                <Panel
                  title="O que o CPC espera desta temporada"
                  actions={<ProvenanceBadge basis="modeled" />}
                  footnote={
                    outlook.data?.disponivel
                      ? `${outlook.data.autoria} Emitido em ${outlook.data.issued}.`
                      : undefined
                  }
                >
                  {outlook.data?.disponivel ? (
                    <Stack gap={3}>
                      <p className="t-body">{outlook.data.synopsis}</p>
                      <ul className="lista-desloc">
                        {(outlook.data.probabilities ?? []).map((p) => (
                          <li key={p.claim}>
                            <span className="t-small">{p.claim}</span>
                            <span className="t-data">{p.percent}%</span>
                            <span className="t-note">CPC</span>
                          </li>
                        ))}
                      </ul>
                      <p className="t-note">
                        Previsao EXTERNA, consumida como contexto (ADR-012). Nao alimenta nenhum
                        bloco de feature e nao e previsao desta engine.
                      </p>
                    </Stack>
                  ) : (
                    <p className="t-small">Boletim do CPC indisponivel.</p>
                  )}
                </Panel>
              </Grid>
            </Section>
          </>
        )}
      </QueryState>
    </View>
  );
}
