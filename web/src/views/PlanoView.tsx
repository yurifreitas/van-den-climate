import { useMemo, useState } from 'react';
import type { CSSProperties } from 'react';
import { usePlano } from '../api/hooks';
import type { AcaoPlano, Cenario } from '../api/types';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { QueryState } from '../components/QueryState';
import { Grid, Panel, Row, Section, Stack, View } from '../components/ui';
import { NIVEL, NIVEL_LABEL } from '../theme/palette';
import './PlanoView.css';

/**
 * Rota `/plano` — a ultima traducao da central.
 *
 * Todas as outras telas diagnosticam. Esta diz o que fazer, onde, e antes de
 * quando. A regra que a organiza inteira: **cada acao mostra a evidencia que
 * a disparou**, no mesmo cartao, sem clique. Uma lista de recomendacoes sem
 * a linha do dado ao lado e opiniao com aparencia de sistema; com a linha, e
 * auditavel e contestavel — a prefeitura aponta e diz "isso mudou".
 *
 * A leitura primaria e o AGREGADO, nao o ranking. Um gestor estadual precisa
 * saber "206 municipios precisam estruturar apoio psicologico" antes de
 * "Restinga Seca precisa de quatro coisas": a primeira e uma politica, a
 * segunda e um oficio.
 */

const HORIZONTES = [
  { id: 'imediato' as const, label: 'Antes de OND/2026', sub: 'ato administrativo, contrato, treinamento' },
  { id: 'estrutural' as const, label: '2027 e adiante', sub: 'ciclo orcamentario, projeto, obra' },
];

const CENARIOS: { id: Cenario; label: string }[] = [
  { id: 'atual', label: 'Agora' },
  { id: 'ond2026', label: 'OND 2026' },
  { id: 'estrutural', label: '2027 +' },
];

const ESFORCO_LARGURA: Record<string, string> = { baixo: '33%', medio: '66%', alto: '100%' };

export function PlanoView() {
  const [cenario, setCenario] = useState<Cenario>('atual');
  const { data, isLoading, isError } = usePlano(cenario);
  const [aberto, setAberto] = useState<number | null>(null);

  const municipiosComAcao = useMemo(
    () => (data?.municipios ?? []).filter((m) => m.acoes.length > 0),
    [data],
  );

  return (
    <View
      title="Plano"
      intro="De lacuna declarada para acao nomeada: o que fazer, onde, e antes de quando. Cada item traz a linha do dado que o disparou."
      actions={
        <div className="camadas" role="group" aria-label="horizonte do indice">
          {CENARIOS.map((c) => (
            <button
              key={c.id}
              type="button"
              className={`camadas__btn${cenario === c.id ? ' camadas__btn--ativo' : ''}`}
              onClick={() => setCenario(c.id)}
              aria-pressed={cenario === c.id}
            >
              {c.label}
            </button>
          ))}
        </div>
      }
    >
      <p className="aviso-escopo t-note">
        Nao e plano de engenharia: sem projeto, custo, prazo ou dimensionamento. Nao substitui o
        Plano Municipal de Reducao de Riscos nem o plano de contingencia da Defesa Civil — aponta a
        ausencia deles. Toda acao sai de dado declarado; nenhuma e inferida.
      </p>

      <QueryState isLoading={isLoading} isError={isError}>
        {data && (
          <>
            <Section title="O plano em numeros">
              <Grid min={210}>
                <Numero n={data.n_com_acao} de={data.n_municipios} label="municipios com pelo menos uma acao" />
                <Numero n={data.n_acoes_total} label="acoes identificadas no estado" />
                <Numero
                  n={data.n_imediatas_total}
                  label="cabem antes da primavera"
                  nota="ato administrativo, contrato ou treinamento — nao dependem de obra"
                />
                <Numero
                  n={data.n_acoes_total - data.n_imediatas_total}
                  label="exigem ciclo orcamentario"
                  nota="projeto ou obra — planejaveis para 2027 sem depender de previsao"
                />
              </Grid>
            </Section>

            {/* Agregado primeiro: e a leitura de quem decide politica. */}
            {HORIZONTES.map((h) => {
              const acoes = data.por_acao
                .filter((a) => a.horizonte === h.id && a.n_municipios > 0)
                .sort((a, b) => b.n_municipios - a.n_municipios);
              if (acoes.length === 0) return null;
              return (
                <Section key={h.id} title={h.label} note={h.sub}>
                  <Stack gap={3}>
                    {acoes.map((a) => (
                      <div key={a.id} className="acao-agregada">
                        <Row>
                          <span className="acao-agregada__titulo t-body">{a.titulo}</span>
                          <span className="acao-agregada__n t-hero">{a.n_municipios}</span>
                        </Row>
                        <div
                          className="acao-agregada__barra"
                          style={
                            {
                              '--frac': `${(a.n_municipios / data.n_municipios) * 100}%`,
                            } as CSSProperties
                          }
                          role="presentation"
                        />
                        <Row>
                          <span className="t-note">
                            {a.detalhe} · {a.populacao_coberta.toLocaleString('pt-BR')} habitantes ·
                            fonte {a.fonte}
                          </span>
                          <span className="esforco t-note">
                            esforco
                            <span className="esforco__trilho">
                              <span
                                className="esforco__nivel"
                                style={{ width: ESFORCO_LARGURA[a.esforco] }}
                              />
                            </span>
                            {a.esforco}
                          </span>
                        </Row>
                      </div>
                    ))}
                  </Stack>
                </Section>
              );
            })}

            <Section
              title="Por municipio, na ordem do plano"
              note={`Ordenado por ${data.regras.ordenacao}. Clique para abrir as acoes e a evidencia de cada uma.`}
            >
              <Stack gap={2}>
                {municipiosComAcao.slice(0, 40).map((m) => {
                  const expandido = aberto === m.cod_mun;
                  return (
                    <div key={m.cod_mun} className="mun-plano" data-aberto={expandido ? 'sim' : undefined}>
                      <button
                        type="button"
                        className="mun-plano__cabeca"
                        onClick={() => setAberto(expandido ? null : m.cod_mun)}
                        aria-expanded={expandido}
                      >
                        <span
                          className="mun-plano__marca"
                          style={{ background: m.level ? NIVEL[m.level] : 'var(--bruma)' }}
                        />
                        <span className="mun-plano__nome">{m.municipio}</span>
                        <span className="t-note mun-plano__nivel">
                          {m.level ? NIVEL_LABEL[m.level] : '—'}
                        </span>
                        <span className="t-data">{m.score?.toFixed(1) ?? '—'}</span>
                        <span className="mun-plano__contagem t-note">
                          {m.n_acoes} {m.n_acoes === 1 ? 'acao' : 'acoes'}
                          {m.n_imediatas > 0 && ` · ${m.n_imediatas} imediata${m.n_imediatas > 1 ? 's' : ''}`}
                        </span>
                        <span className="mun-plano__seta" aria-hidden="true">
                          {expandido ? '−' : '+'}
                        </span>
                      </button>
                      {expandido && (
                        <div className="mun-plano__corpo">
                          {m.acoes.map((a) => (
                            <CartaoAcao key={a.id} a={a} />
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </Stack>
              {municipiosComAcao.length > 40 && (
                <p className="t-note">
                  Mostrando os 40 primeiros de {municipiosComAcao.length} municipios com acao. O
                  corte e de leitura, nao do plano — a API devolve todos.
                </p>
              )}
            </Section>

            <Section title="Limites deste plano">
              <Panel tone="verdict">
                <ul className="lista-marcas" data-tom="alerta">
                  {data.limites.map((l) => (
                    <li key={l}>{l}</li>
                  ))}
                </ul>
              </Panel>
            </Section>
          </>
        )}
      </QueryState>
    </View>
  );
}

/** Acao + a linha do dado que a disparou, sempre juntas e sem clique. */
function CartaoAcao({ a }: { a: AcaoPlano }) {
  return (
    <div className="acao" data-horizonte={a.horizonte}>
      <Row>
        <span className="acao__titulo t-small">{a.titulo}</span>
        <span className="acao__tags t-note">
          {a.horizonte} · esforco {a.esforco}
        </span>
      </Row>
      <p className="acao__evidencia t-note">{a.evidencia}</p>
      <Row>
        <span className="t-note">{a.detalhe}</span>
        <ProvenanceBadge basis={a.basis} />
      </Row>
    </div>
  );
}

function Numero({
  n,
  de,
  label,
  nota,
}: {
  n: number;
  de?: number;
  label: string;
  nota?: string;
}) {
  return (
    <Panel>
      <Row>
        <span className="t-hero">{n.toLocaleString('pt-BR')}</span>
        {de !== undefined && <span className="t-note">de {de}</span>}
      </Row>
      <p className="t-small">{label}</p>
      {nota && <p className="t-note">{nota}</p>}
    </Panel>
  );
}
