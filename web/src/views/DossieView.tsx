import { useMemo, useState } from 'react';
import type { CSSProperties } from 'react';
import { useDossie, useMunicipalRisk } from '../api/hooks';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { QueryState } from '../components/QueryState';
import { Empty, Field, Grid, Panel, Row, Section, Stack, View } from '../components/ui';
import { NIVEL, NIVEL_LABEL } from '../theme/palette';
import './DossieView.css';

/**
 * Rota `/dossie` — o painel de decisao.
 *
 * As dez camadas da central reunidas para UM municipio, na ordem em que a
 * decisao acontece e nao na ordem em que foram construidas:
 *
 *   1. onde estou      2. qual o perigo     3. quem esta exposto
 *   4. com o que conto 5. o que falhou      6. o que fazer
 *   7. o que nao sei
 *
 * A numeracao aparece na tela de proposito. Um painel de decisao sem ordem
 * declarada vira lista de widgets, e cada leitor inventa a propria sequencia.
 *
 * O bloco 7 tem o mesmo peso visual dos outros. Quem decide sem saber o que a
 * central NAO sabe decide pior do que quem nao a consultou.
 */

const ROTULO_GRUPO: Record<string, string> = {
  criancas: 'criancas',
  gestantes: 'gestantes',
  'pessoas com doencas cronicas': 'pessoas com doencas cronicas',
};

export function DossieView() {
  const lista = useMunicipalRisk('atual');
  const [cod, setCod] = useState<number | null>(null);
  const dossie = useDossie(cod);

  const municipios = useMemo(
    () => [...(lista.data?.municipios ?? [])].sort((a, b) => a.municipio.localeCompare(b.municipio)),
    [lista.data],
  );

  const d = dossie.data;

  return (
    <View
      title="Dossie"
      intro="Tudo o que a central sabe sobre um municipio, num lugar so, na ordem em que a decisao acontece."
      actions={
        <Field label="Municipio">
          <select
            value={cod ?? ''}
            onChange={(e) => setCod(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">selecione…</option>
            {municipios.map((m) => (
              <option key={m.cod_mun} value={m.cod_mun}>
                {m.municipio}
              </option>
            ))}
          </select>
        </Field>
      }
    >
      {cod === null ? (
        <Empty>
          Escolha um municipio. O dossie reune as dez camadas da central — indice, memoria hidrica,
          geotecnico, recursos, pessoal, territorios tradicionais, plano e lacunas — organizadas
          pela ordem da decisao, nao pela ordem em que foram construidas.
        </Empty>
      ) : (
        <QueryState isLoading={dossie.isLoading} isError={dossie.isError}>
          {d && (
            <>
              {/* 1 ------------------------------------------------------- */}
              <div className="dossie-hero" data-nivel={d.posicao.nivel ?? undefined}>
                <div>
                  <span className="t-section">1 · Onde estou</span>
                  <p className="dossie-hero__nome t-display">{d.municipio}</p>
                  <p className="t-small">
                    {d.posicao.populacao?.toLocaleString('pt-BR') ?? '—'} habitantes
                    {d.posicao.regime_cheia?.regime && (
                      <> · bacia {d.posicao.regime_cheia.bacia}</>
                    )}
                  </p>
                </div>
                <div className="dossie-hero__indice">
                  <span className="t-hero">{d.posicao.indice?.toFixed(1) ?? '—'}</span>
                  <span
                    className="dossie-hero__nivel"
                    style={
                      { '--nivel-cor': d.posicao.nivel ? NIVEL[d.posicao.nivel] : 'var(--bruma)' } as CSSProperties
                    }
                  >
                    {d.posicao.nivel ? NIVEL_LABEL[d.posicao.nivel] : 'SEM BASE'}
                  </span>
                  <span className="t-note">
                    {d.posicao.posicao_no_ranking
                      ? `${d.posicao.posicao_no_ranking}º de ${d.posicao.de}`
                      : 'fora do ranking'}
                  </span>
                </div>
                {d.posicao.regime_cheia?.regime && (
                  <div className="dossie-hero__regime">
                    <span className="t-section">Regime de cheia</span>
                    <p className="dossie-hero__regime-nome">
                      {d.posicao.regime_cheia.regime.replace(/_/g, ' ')}
                    </p>
                    <p className="t-note">
                      {d.posicao.regime_cheia.regime === 'lagunar'
                        ? 'Nivel governado por VENTO, nao por chuva local. Drenagem por gravidade falha quando a laguna sobe.'
                        : d.posicao.regime_cheia.regime === 'fluvial_com_remanso'
                          ? 'Cheia rapida propria somada ao represamento do trecho baixo pelo Guaiba.'
                          : 'Drena para o Uruguai ou e cabeceira. Vento nao entra.'}
                    </p>
                  </div>
                )}
              </div>

              {/* 2 ------------------------------------------------------- */}
              <Section title="2 · Qual o perigo">
                <Grid min={240}>
                  <Painel titulo="Componentes do indice">
                    <Barras componentes={d.perigo.componentes} />
                  </Painel>
                  <Painel titulo="Memoria hidrica" basis={d.perigo.memoria_hidrica?.basis ?? null}>
                    {d.perigo.memoria_hidrica ? (
                      <>
                        <p className="t-hero">
                          {d.perigo.memoria_hidrica.memoria_hidrica_frac === null
                            ? '—'
                            : `${(d.perigo.memoria_hidrica.memoria_hidrica_frac * 100).toFixed(1)}%`}
                        </p>
                        <p className="t-small">
                          do territorio ja foi agua entre 1984 e 2021 e hoje nao e
                        </p>
                      </>
                    ) : (
                      <p className="t-note">camada nao calculada</p>
                    )}
                  </Painel>
                  <Painel titulo="Encosta e talude" basis={d.perigo.geotecnico?.basis ?? null}>
                    {d.perigo.geotecnico?.ocorrencias?.length ? (
                      <ul className="lista-marcas" data-tom="alerta">
                        {d.perigo.geotecnico.ocorrencias.map((o) => (
                          <li key={o}>{o}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="t-small">Nenhuma ocorrencia geotecnica declarada.</p>
                    )}
                  </Painel>
                  <Painel
                    titulo="Impermeabilizacao"
                    basis={d.perigo.impermeabilizacao?.basis ?? null}
                  >
                    {d.perigo.impermeabilizacao?.frac_construida != null ? (
                      <>
                        <p className="t-hero">
                          {(d.perigo.impermeabilizacao.frac_construida * 100).toFixed(1)}%
                        </p>
                        <p className="t-small">
                          da area do municipio e superficie construida
                          {d.perigo.impermeabilizacao.acima_do_limiar && (
                            <> — entre os 10% mais impermeabilizados do RS</>
                          )}
                        </p>
                        {/* Sem esta nota o numero convida a comparacao com os
                            10-25% da literatura, que sao de BACIA. */}
                        <p className="t-note">{d.perigo.impermeabilizacao.nota}</p>
                      </>
                    ) : (
                      <p className="t-note">camada nao calculada</p>
                    )}
                  </Painel>
                  <Painel titulo="Acesso" basis={d.perigo.acesso?.basis ?? null}>
                    <ul className="lista-marcas">
                      <li>
                        dano viario em 2024: <strong>{sim(d.perigo.acesso?.dano_viario)}</strong>
                      </li>
                      <li>
                        ficou ilhado: <strong>{sim(d.perigo.acesso?.ficou_ilhado)}</strong>
                      </li>
                      <li>
                        dano a barragem: <strong>{sim(d.perigo.barragem?.dano_declarado)}</strong>
                      </li>
                    </ul>
                  </Painel>
                </Grid>
              </Section>

              {/* 3 ------------------------------------------------------- */}
              <Section
                title="3 · Quem esta exposto"
                note="Grupos declarados ao IBGE como atingidos em 2024, e territorios tradicionais mapeados."
              >
                <Grid min={300}>
                  <Painel
                    titulo="Grupos atingidos"
                    basis={d.exposicao.grupos_vulneraveis?.basis ?? null}
                  >
                    {d.exposicao.grupos_vulneraveis?.grupos?.length ? (
                      <ul className="lista-marcas" data-tom="alerta">
                        {d.exposicao.grupos_vulneraveis.grupos.map((gr) => (
                          <li key={gr}>{ROTULO_GRUPO[gr] ?? gr}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="t-small">Nenhum grupo declarado.</p>
                    )}
                  </Painel>
                  <Painel titulo={`Territorios tradicionais (${d.exposicao.n_territorios})`}>
                    {d.exposicao.territorios_tradicionais.length === 0 ? (
                      <p className="t-small">
                        Nenhum territorio mapeado com centroide neste municipio. Territorio sem
                        processo aberto nao aparece — ausencia aqui nao prova ausencia.
                      </p>
                    ) : (
                      <Stack gap={2}>
                        {d.exposicao.territorios_tradicionais.map((t) => (
                          <div key={`${t.tipo}-${t.nome}`} className="territorio">
                            <Row>
                              <span className="territorio__nome">{t.nome ?? '(sem nome)'}</span>
                              <span className="t-note">{t.tipo}</span>
                            </Row>
                            <p className="t-note">
                              {t.grupo_etnico && `${t.grupo_etnico} · `}
                              {t.situacao_juridica}
                              {t.memoria_hidrica_frac !== null &&
                                ` · ${(t.memoria_hidrica_frac * 100).toFixed(1)}% ja foi agua`}
                              {t.km_ate_urgencia !== null && ` · ${km(t.km_ate_urgencia)} ate urgencia`}
                            </p>
                          </div>
                        ))}
                      </Stack>
                    )}
                  </Painel>
                </Grid>
              </Section>

              {/* 4 ------------------------------------------------------- */}
              <Section title="4 · Com o que conto">
                <Grid min={230}>
                  <Painel titulo="Saude instalada" basis={d.capacidade.saude?.basis ?? null}>
                    {d.capacidade.saude ? (
                      <ul className="lista-marcas">
                        <li>
                          {d.capacidade.saude.total} {d.capacidade.saude.unidade}
                        </li>
                        <li>{d.capacidade.saude.hospitais} hospitalar, {d.capacidade.saude.urgencia} urgencia</li>
                        {d.capacidade.saude.km_ate_unidade_mais_proxima !== null && (
                          <li className="marca-falta">
                            nenhuma no municipio — {km(d.capacidade.saude.km_ate_unidade_mais_proxima)}
                          </li>
                        )}
                      </ul>
                    ) : (
                      <p className="t-note">—</p>
                    )}
                  </Painel>
                  <Painel titulo="Travessias">
                    {d.capacidade.pontes ? (
                      <>
                        <p className="t-hero">{d.capacidade.pontes.n_malha_principal}</p>
                        <p className="t-small">
                          na malha principal, {d.capacidade.pontes.n_estruturantes} estruturantes
                        </p>
                        <p className="t-note">{d.capacidade.pontes.nota}</p>
                      </>
                    ) : (
                      <p className="t-note">—</p>
                    )}
                  </Painel>
                  <Painel titulo="Quadro de pessoal" basis={d.capacidade.quadro_pessoal?.basis ?? null}>
                    {d.capacidade.quadro_pessoal ? (
                      <ul className="lista-marcas">
                        <li>{d.capacidade.quadro_pessoal.total ?? '—'} servidores</li>
                        <li>
                          {d.capacidade.quadro_pessoal.por_mil_hab?.toFixed(1) ?? '—'} por mil hab
                        </li>
                        {d.capacidade.quadro_pessoal.quadro_fragil && (
                          <li className="marca-falta">
                            quadro fragil:{' '}
                            {((d.capacidade.quadro_pessoal.frac_sem_estabilidade ?? 0) * 100).toFixed(0)}%
                            sem vinculo permanente
                          </li>
                        )}
                      </ul>
                    ) : (
                      <p className="t-note">—</p>
                    )}
                  </Painel>
                  <Painel titulo="Voluntariado">
                    {d.capacidade.voluntariado?.km_brigada_mais_proxima !== null &&
                    d.capacidade.voluntariado !== null ? (
                      <>
                        <p className="t-hero">
                          {km(d.capacidade.voluntariado.km_brigada_mais_proxima!)}
                        </p>
                        <p className="t-small">ate a brigada voluntaria mais proxima</p>
                      </>
                    ) : (
                      <p className="t-note">nenhuma brigada identificada</p>
                    )}
                  </Painel>
                </Grid>
              </Section>

              {/* 5 ------------------------------------------------------- */}
              <Section
                title="5 · O que falhou em 2024"
                note="Declarado pelo proprio municipio ao IBGE no evento de 26/04/2024."
              >
                <Grid min={280}>
                  <Painel titulo="Prevencao" basis={d.falhas_2024.deficit_prevencao.basis}>
                    {(d.falhas_2024.deficit_prevencao.detalhe.lacunas ?? []).length ? (
                      <ul className="lista-marcas" data-tom="alerta">
                        {d.falhas_2024.deficit_prevencao.detalhe.lacunas!.map((l) => (
                          <li key={l}>{l}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="t-small">Nenhuma lacuna declarada.</p>
                    )}
                  </Painel>
                  <Painel titulo="Sistema de saude" basis={d.falhas_2024.saude_afetada?.basis ?? null}>
                    {d.falhas_2024.saude_afetada?.impactos?.length ? (
                      <ul className="lista-marcas" data-tom="alerta">
                        {d.falhas_2024.saude_afetada.impactos.map((i) => (
                          <li key={i}>{i}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="t-small">Nenhum impacto declarado.</p>
                    )}
                  </Painel>
                  <Painel titulo="Autonomia logistica">
                    {d.falhas_2024.autonomia_logistica?.indice !== null &&
                    d.falhas_2024.autonomia_logistica ? (
                      <>
                        <p className="t-hero">
                          {d.falhas_2024.autonomia_logistica.indice!.toFixed(2)}
                        </p>
                        <p className="t-small">
                          em {d.falhas_2024.autonomia_logistica.n_aplicaveis} de 7 escalas aplicaveis
                        </p>
                      </>
                    ) : (
                      <p className="t-small">Nenhuma escala aplicavel — nao foi testado.</p>
                    )}
                    <p className="t-note">
                      Apoio psicologico:{' '}
                      {d.falhas_2024.resposta_prestada?.apoio_psicologico === false ? (
                        <strong className="marca-falta">nao ofereceu</strong>
                      ) : d.falhas_2024.resposta_prestada?.apoio_psicologico ? (
                        'ofereceu'
                      ) : (
                        'nao informado'
                      )}
                    </p>
                  </Painel>
                </Grid>
              </Section>

              {/* 6 ------------------------------------------------------- */}
              <Section
                title={`6 · O que fazer (${d.acao.n_acoes} acoes, ${d.acao.n_imediatas} imediatas)`}
                note="Cada acao traz a linha do dado que a disparou. Nenhuma e inferida."
              >
                {d.acao.acoes.length === 0 ? (
                  <Empty>Nenhuma acao disparada pelos dados declarados deste municipio.</Empty>
                ) : (
                  <Stack gap={2}>
                    {d.acao.acoes.map((a) => (
                      <div key={a.id} className="acao" data-horizonte={a.horizonte}>
                        <Row>
                          <span className="acao__titulo t-small">{a.titulo}</span>
                          <span className="acao__tags t-note">
                            {a.horizonte} · esforco {a.esforco}
                          </span>
                        </Row>
                        <p className="acao__evidencia t-note">{a.evidencia}</p>
                      </div>
                    ))}
                  </Stack>
                )}

                {d.acao.estrategias_contencao.length > 0 && (
                  <>
                    <p className="t-note estrategia-nota">
                      Estrategias de contencao cabiveis, com a alternativa convencional e a baseada
                      na natureza lado a lado. Nenhuma e superior por natureza — sao diferentes, e
                      o custo de cada lado esta nomeado.
                    </p>
                    <Stack gap={3}>
                      {d.acao.estrategias_contencao.map((e) => (
                        <div key={e.id} className="estrategia">
                          <Row>
                            <span className="estrategia__titulo">{e.titulo}</span>
                            <span className="t-note">{e.mecanismo}</span>
                          </Row>
                          <p className="acao__evidencia t-note">{e.evidencia}</p>
                          <div className="estrategia__par">
                            <div>
                              <span className="t-section">Convencional</span>
                              <p className="t-small">{e.convencional}</p>
                            </div>
                            <div className="estrategia__natureza">
                              <span className="t-section">Baseada na natureza</span>
                              <p className="t-small">{e.natureza}</p>
                              <p className="t-note">
                                <strong>Ganha quando:</strong> {e.quando_natureza_ganha}
                              </p>
                              <p className="t-note">
                                <strong>Nao resolve:</strong> {e.limite}
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </Stack>
                  </>
                )}
              </Section>

              {/* 7 ------------------------------------------------------- */}
              <Section
                title="7 · O que esta central NAO sabe sobre este municipio"
                note="Mesmo peso dos blocos acima. Decidir sem saber o que falta e pior que nao consultar."
              >
                <Grid min={280}>
                  {d.lacunas.map((l) => (
                    <Panel key={`${l.camada}-${l.id}`} title={l.titulo} tone="verdict">
                      <p className="t-small">{l.motivo}</p>
                      <Row>
                        <span className="t-note">camada: {l.camada}</span>
                        <ProvenanceBadge basis={null} />
                      </Row>
                    </Panel>
                  ))}
                </Grid>
              </Section>
            </>
          )}
        </QueryState>
      )}
    </View>
  );
}

/**
 * Distancia em km. Abaixo de 10 km mantem a casa decimal: arredondar 0,4 km
 * para "0 km" transforma "ha uma unidade a quatrocentos metros" em "a unidade
 * esta aqui dentro", que sao coisas diferentes num territorio isolado.
 */
function km(v: number): string {
  return v < 10 ? `${v.toFixed(1)} km` : `${v.toFixed(0)} km`;
}

function sim(v: boolean | null | undefined): string {
  if (v === null || v === undefined) return 'nao informado';
  return v ? 'sim' : 'nao';
}

function Painel({
  titulo,
  basis,
  children,
}: {
  titulo: string;
  basis?: import('../api/types').Basis | null;
  children: React.ReactNode;
}) {
  return (
    <Panel title={titulo} actions={basis !== undefined ? <ProvenanceBadge basis={basis} /> : undefined}>
      {children}
    </Panel>
  );
}

/** Barras dos quatro componentes do indice, com ausente hachurado. */
function Barras({ componentes }: { componentes: MunicipioRiscoComponentes }) {
  const itens = [
    { k: 'impacto', label: 'Impacto hidrico 2024' },
    { k: 'deficit_prevencao', label: 'Deficit de prevencao' },
    { k: 'exposicao', label: 'Exposicao' },
    { k: 'perigo_sazonal', label: 'Perigo sazonal' },
  ] as const;
  return (
    <div className="comp-barras">
      {itens.map(({ k, label }) => {
        const c = componentes[k];
        const ausente = c.valor === null;
        return (
          <div key={k} className="comp-barra">
            <Row>
              <span className="t-small">{label}</span>
              <span className="t-data">{ausente ? '—' : c.valor!.toFixed(2)}</span>
            </Row>
            <span
              className="comp-barra__trilho"
              data-ausente={ausente ? 'sim' : undefined}
              style={{ '--frac': `${(c.valor ?? 0) * 100}%` } as CSSProperties}
            />
          </div>
        );
      })}
    </div>
  );
}

type MunicipioRiscoComponentes = import('../api/types').MunicipioRisco['componentes'];
