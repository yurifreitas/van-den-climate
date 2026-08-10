import { useMemo, useState } from 'react';
import { useMalhaMunicipal, useMunicipalRisk, usePessoal, useRecursos } from '../api/hooks';
import { MapaMunicipal, pontosDesenhados } from '../components/MapaMunicipal';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { QueryState } from '../components/QueryState';
import { DataTable, Empty, Grid, Panel, Row, Section, Stack, View } from '../components/ui';
import type { Column } from '../components/ui';
import type { VazioCobertura } from '../api/types';
import { CATEGORICO } from '../theme/palette';
import './RecursosView.css';

/**
 * Rota `/recursos` — onde estao os meios de resposta, e onde falta.
 *
 * A tela existe para uma pergunta operacional: antes da temporada, para onde
 * deslocar. Ela responde com o mais perto disso que o dado publico sustenta —
 * o cruzamento de risco com vazio de cobertura — e recusa explicitamente a
 * resposta que o usuario espera de um sistema assim: "mova N viaturas de A
 * para B". Essa exigiria frota, malha viaria e modelo de tempo-resposta, e
 * nenhum dos tres existe em base publica.
 *
 * A ressalva nao fica em rodape. Ela abre a tela, porque um mapa de pontos
 * comunica precisao logistica que este dado nao tem.
 */

/**
 * Cor por FAMILIA, nao por papel — e a mudanca veio de uma restricao dura da
 * paleta, nao de gosto.
 *
 * O categorico do projeto tem seis cores, validadas duas a duas sob
 * deuteranopia, e a regra e explicita: nunca cicla, a setima categoria vira
 * "Outros" (DESIGN.md §1). Com dezessete papeis no mapa, colorir por papel
 * exigiria reciclar cor — o que faria escola e subestacao dividirem o mesmo
 * tom e destruiria a unica coisa que a cor categorica deve garantir, que e
 * identidade.
 *
 * Cinco familias cabem nas seis cores com folga. Dentro da familia a
 * distincao fica no rotulo e no filtro, que e onde ela e de fato usada: quem
 * olha o mapa quer ver "onde esta o socorro", nao distinguir CAPS de
 * pronto-socorro a olho nu.
 */
const CORES_FAMILIA: Record<string, string> = {
  socorro: CATEGORICO[0],
  abrigo: CATEGORICO[1],
  acesso: CATEGORICO[2],
  infraestrutura: CATEGORICO[3],
  suprimento: CATEGORICO[4],
};

/**
 * Ordem dentro de cada familia. As familias existem porque os papeis NAO se
 * somam: hospital e supermercado respondem perguntas diferentes, e um "total
 * de recursos" misturando os dois nao significaria nada. O mapa comeca com
 * socorro ligado e o resto desligado — dezessete camadas acesas de uma vez
 * viram mancha, e a leitura util e uma familia por vez.
 */
const ORDEM_POR_FAMILIA: Record<string, string[]> = {
  socorro: [
    'fixo_hospitalar',
    'fixo_urgencia',
    'regulacao',
    'movel',
    'psicossocial',
    'bombeiro',
    'policia',
  ],
  abrigo: ['abrigo_escola', 'abrigo_comunitario', 'abrigo_religioso'],
  acesso: ['heliponto', 'aerodromo'],
  infraestrutura: ['energia_subestacao', 'agua_tratamento', 'agua_reservatorio'],
  suprimento: ['combustivel', 'alimento'],
};

const ORDEM_PAPEL = Object.values(ORDEM_POR_FAMILIA).flat();

/** Ligadas no primeiro render. Ver o comentario acima. */
const FAMILIA_INICIAL = 'socorro';

/** Cartao de numero. Duplicado de PlanoView de proposito? Nao — extraido aqui
 *  porque as duas telas ja o usavam; se aparecer uma terceira, vira primitiva. */
function Numero({
  n,
  de,
  label,
  nota,
  tom,
}: {
  n: number;
  de?: number;
  label: string;
  nota?: string;
  tom?: 'falta';
}) {
  return (
    <Panel>
      <Row>
        <span className="t-hero" data-tom={tom}>
          {n.toLocaleString('pt-BR')}
        </span>
        {de !== undefined && <span className="t-note">de {de}</span>}
      </Row>
      <p className="t-small">{label}</p>
      {nota && <p className="t-note">{nota}</p>}
    </Panel>
  );
}

export function RecursosView() {
  const recursos = useRecursos();
  const pessoal = usePessoal();
  const malha = useMalhaMunicipal();
  const risco = useMunicipalRisk('atual');
  const [visiveis, setVisiveis] = useState<Set<string>>(
    new Set(ORDEM_POR_FAMILIA[FAMILIA_INICIAL]),
  );

  /** papel -> cor, resolvido pela familia que o payload declara. */
  const CORES = useMemo(() => {
    const mapa: Record<string, string> = {};
    for (const [papel, info] of Object.entries(recursos.data?.resumo.por_papel ?? {})) {
      mapa[papel] = CORES_FAMILIA[info.familia] ?? CATEGORICO[5];
    }
    return mapa;
  }, [recursos.data]);

  const pontosFiltrados = useMemo(
    () => (recursos.data?.pontos ?? []).filter((p) => visiveis.has(p.papel)),
    [recursos.data, visiveis],
  );

  /** Liga/desliga uma familia inteira — o modo em que o mapa e legivel. */
  const alternarFamilia = (familia: string) =>
    setVisiveis((s) => {
      const papeis = ORDEM_POR_FAMILIA[familia] ?? [];
      const todosLigados = papeis.every((p) => s.has(p));
      const n = new Set(s);
      for (const p of papeis) {
        if (todosLigados) n.delete(p);
        else n.add(p);
      }
      return n;
    });

  const alternar = (papel: string) =>
    setVisiveis((s) => {
      const n = new Set(s);
      if (n.has(papel)) n.delete(papel);
      else n.add(papel);
      return n;
    });

  const colunasVazio: Column<VazioCobertura>[] = [
    {
      key: 'municipio',
      header: 'Municipio',
      cell: (v) => v.municipio,
      sortValue: (v) => v.municipio,
    },
    {
      key: 'score',
      header: 'Indice',
      align: 'num',
      cell: (v) => v.score?.toFixed(1) ?? '—',
      sortValue: (v) => v.score ?? -1,
    },
    {
      key: 'faltas',
      header: 'Recurso critico mais proximo',
      cell: (v) => (
        <span className="faltas">
          {v.faltas.map((f) => (
            <span key={f.papel} className="falta">
              <span className="falta__marca" style={{ background: CORES[f.papel] }} />
              {f.label} <strong>{f.km?.toFixed(0)} km</strong>
              {f.completude === 'colaborativa' && <span className="t-note"> (OSM)</span>}
            </span>
          ))}
        </span>
      ),
    },
    {
      key: 'pior',
      header: 'Pior',
      align: 'num',
      cell: (v) => `${v.pior_km.toFixed(0)} km`,
      sortValue: (v) => v.pior_km,
    },
    {
      key: 'pop',
      header: 'Populacao',
      align: 'num',
      cell: (v) => v.populacao?.toLocaleString('pt-BR') ?? '—',
      sortValue: (v) => v.populacao ?? -1,
    },
  ];

  return (
    <View
      title="Recursos"
      intro="Onde estao os meios de resposta do estado, e onde o vazio de cobertura encontra o risco mais alto."
    >
      <p className="aviso-escopo t-note">
        <strong>E base, nunca viatura.</strong> Nao existe dado publico de frota — de ambulancia, de
        viatura policial ou de caminhao de bombeiro. Esta tela mostra ONDE ha unidade instalada e a
        que distancia ela esta, nunca quantos veiculos operam. &quot;Realocar&quot; aqui significa
        onde o vazio e maior diante do risco; dizer &quot;mova N carros de A para B&quot; exigiria
        frota, malha viaria e modelo de tempo-resposta que esta engine nao tem.
      </p>

      <QueryState
        isLoading={recursos.isLoading || malha.isLoading}
        isError={recursos.isError || malha.isError}
      >
        {recursos.data && malha.data && (
          <>
            <Section
              title="Mapa geral dos recursos"
              note="Clique nos rotulos para ligar e desligar camadas. Distancias sao linha reta sobre o centroide municipal — piso da dificuldade de acesso, nunca tempo de rota."
            >
              <Panel pad="tight">
                {Object.entries(ORDEM_POR_FAMILIA).map(([familia, papeis]) => (
                  <div key={familia} className="recursos-familia">
                    <button
                      type="button"
                      className="recursos-familia__titulo"
                      onClick={() => alternarFamilia(familia)}
                      aria-pressed={papeis.every((p) => visiveis.has(p))}
                    >
                      <span
                        className="recursos-legenda__marca"
                        style={{ background: CORES_FAMILIA[familia] }}
                      />
                      {recursos.data.resumo.familias?.[familia] ?? familia}
                    </button>
                    <div className="recursos-legenda">
                      {papeis.map((papel) => {
                        const info = recursos.data.resumo.por_papel[papel];
                        if (!info) return null;
                        const ligado = visiveis.has(papel);
                        return (
                          <button
                            key={papel}
                            type="button"
                            className={`recursos-legenda__item${ligado ? '' : ' recursos-legenda__item--off'}`}
                            onClick={() => alternar(papel)}
                            aria-pressed={ligado}
                          >
                            <span
                              className="recursos-legenda__marca"
                              style={{ background: CORES[papel] }}
                            />
                            {info.label}
                            <strong>{info.n}</strong>
                            {info.completude !== 'cadastro' && (
                              <span className="t-note">
                                {info.completude === 'colaborativa' ? 'OSM' : 'parcial'}
                              </span>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
                {pontosFiltrados.length > pontosDesenhados(pontosFiltrados.length) && (
                  <p className="footnote">
                    O mapa desenha {pontosDesenhados(pontosFiltrados.length).toLocaleString('pt-BR')}{' '}
                    dos {pontosFiltrados.length.toLocaleString('pt-BR')} pontos ligados — amostra
                    regular, para nao travar o navegador. As contagens na legenda e nas tabelas sao
                    sempre do total; so o desenho e amostrado.
                  </p>
                )}
                <MapaMunicipal
                  malha={malha.data}
                  municipios={risco.data?.municipios ?? []}
                  camada="recursos"
                  selecionado={null}
                  onSelecionar={() => {}}
                  recursos={pontosFiltrados}
                  coresRecurso={CORES}
                />
              </Panel>
            </Section>

            <Section
              title="Onde realocar primeiro"
              note={`Cruzamento de risco com vazio de cobertura. Vazio = recurso critico a ${recursos.data.resumo.limiar_vazio_km} km ou mais.`}
            >
              {/* Selo proprio: o cadastro e medido, a ordem desta lista nao. */}
              <Row>
                <ProvenanceBadge basis={recursos.data.vazios.provenance.basis} />
                <span className="footnote">{recursos.data.vazios.nota}</span>
              </Row>
              {recursos.data.vazios.itens.length === 0 ? (
                <Empty>Nenhum municipio avaliado combina risco e vazio critico.</Empty>
              ) : (
                <DataTable
                  columns={colunasVazio}
                  rows={recursos.data.vazios.itens}
                  rowKey={(v) => v.cod_mun}
                />
              )}
            </Section>

            {recursos.data.resumo.exposicao_hidrica && (
              <Section
                title="O recurso que alaga junto"
                note={recursos.data.resumo.exposicao_hidrica.nota}
              >
                <Grid min={220}>
                  {Object.entries(recursos.data.resumo.exposicao_hidrica.taxa_por_familia).map(
                    ([familia, t]) => (
                      <Panel key={familia} title={t.label}>
                        <Row>
                          <span className="t-hero">
                            {t.taxa === null ? '—' : `${(t.taxa * 100).toFixed(1)}%`}
                          </span>
                          <span
                            className="recursos-legenda__marca"
                            style={{ background: CORES_FAMILIA[familia] }}
                          />
                        </Row>
                        <p className="t-small">
                          {t.n_expostos} de {t.n} pontos sobre area que ja foi agua
                        </p>
                      </Panel>
                    ),
                  )}
                </Grid>
                <p className="footnote">
                  A diferenca entre as familias nao e acaso, e projeto: captacao de agua
                  precisa ficar junto do rio, e subestacao procura terreno plano e barato —
                  que na planicie e a varzea. O que mantem a cidade funcionando foi
                  construido onde a agua passa.
                </p>
                {recursos.data.resumo.exposicao_hidrica.criticos_expostos.length > 0 && (
                  <Panel title="Criticos sobre memoria hidrica — fila de inspecao, nao laudo">
                    <ul className="recursos-expostos">
                      {recursos.data.resumo.exposicao_hidrica.criticos_expostos
                        .slice(0, 12)
                        .map((c) => (
                          <li key={c.id}>
                            <strong>{c.nome ?? `${c.label} sem nome`}</strong>{' '}
                            <span className="t-note">
                              {c.label} · {(c.memoria_hidrica_frac * 100).toFixed(0)}% da celula
                              ja foi agua
                            </span>
                          </li>
                        ))}
                    </ul>
                  </Panel>
                )}
              </Section>
            )}

            <Section title="Cobertura por papel">
              <Grid min={250}>
                {ORDEM_PAPEL.map((papel) => {
                  const info = recursos.data.resumo.por_papel[papel];
                  if (!info) return null;
                  return (
                    <Panel key={papel} title={info.label}>
                      <Stack gap={2}>
                        <Row>
                          <span className="t-hero">{info.n}</span>
                          <span
                            className="recursos-legenda__marca"
                            style={{ background: CORES[papel] }}
                          />
                        </Row>
                        {info.municipios_alem_do_limiar !== null &&
                          info.municipios_alem_do_limiar !== undefined && (
                            <p className="t-small">
                              <strong>{info.municipios_alem_do_limiar}</strong> municipios a{' '}
                              {recursos.data.resumo.limiar_vazio_km} km ou mais do mais proximo
                            </p>
                          )}
                        <p className="t-note">
                          fonte {info.fonte} ·{' '}
                          {info.completude === 'colaborativa'
                            ? 'mapeamento colaborativo'
                            : info.completude === 'cadastro_parcial'
                              ? 'cadastro parcial'
                              : 'cadastro'}
                        </p>
                        <ProvenanceBadge basis="measured" />
                      </Stack>
                    </Panel>
                  );
                })}
              </Grid>
            </Section>

            {pessoal.data && (
              <>
                <Section
                  title="Deficit de pessoal — quem executa o plano"
                  note={pessoal.data.resumo.servidores_por_mil.nota}
                >
                  <Grid min={230}>
                    <Numero
                      n={pessoal.data.resumo.quadro_fragil.n}
                      de={pessoal.data.resumo.n_com_quadro}
                      label="municipios com quadro fragil"
                      nota={`${(pessoal.data.resumo.quadro_fragil.limiar * 100).toFixed(0)}% ou mais do quadro sem vinculo permanente`}
                      tom="falta"
                    />
                    <Numero
                      n={pessoal.data.resumo.sem_concurso_24m}
                      de={pessoal.data.resumo.n_municipios}
                      label="sem concurso nos ultimos 24 meses"
                      nota="capacidade de repor quadro"
                    />
                    <Numero
                      n={pessoal.data.resumo.faltou_pessoal_em_2024}
                      label="declararam falta de pessoal como motivo de nao execucao do plano"
                      nota="motivo declarado ao IBGE no evento de 2024"
                      tom="falta"
                    />
                    <Numero
                      n={pessoal.data.resumo.servidores_por_mil.mediana ?? 0}
                      label="servidores por mil habitantes (mediana)"
                      nota={`varia de ${pessoal.data.resumo.servidores_por_mil.min} a ${pessoal.data.resumo.servidores_por_mil.max}`}
                    />
                  </Grid>
                </Section>

                {/* O achado que muda a estrategia de voluntariado. Fica em
                    painel proprio porque nao e um numero — e a razao de a
                    recomendacao ser "replicar" e nao "criar". */}
                <Section title="Voluntariado — o modelo ja existe no RS">
                  <Panel>
                    <p className="t-body destaque-modelo">
                      {pessoal.data.resumo.voluntariado.modelo_existente}
                    </p>
                    <Row>
                      <span className="t-small">
                        <strong>{pessoal.data.resumo.voluntariado.n_brigadas_identificadas}</strong>{' '}
                        brigadas voluntarias identificadas
                      </span>
                      <span className="t-small">
                        <strong>{pessoal.data.resumo.voluntariado.municipios_a_mais_de_60km}</strong>{' '}
                        municipios a mais de 60 km da mais proxima
                      </span>
                    </Row>
                    <p className="t-note">
                      {pessoal.data.resumo.voluntariado.municipios_com_brigada.slice(0, 12).join(' · ')}
                    </p>
                    <ProvenanceBadge basis="measured" />
                  </Panel>
                </Section>

                <Section
                  title="Auxilio mutuo — com quem conversar"
                  note="Sugere parceiro plausivel dentro de 60 km. 'Folga' e ausencia dos sinais de fragilidade que o dado registra, NAO capacidade ociosa medida."
                >
                  {pessoal.data.auxilio_mutuo.length === 0 ? (
                    <Empty>Nenhum par sugerido com os criterios atuais.</Empty>
                  ) : (
                    <Stack gap={2}>
                      {pessoal.data.auxilio_mutuo.slice(0, 12).map((a) => (
                        <div key={a.cod_mun} className="par-auxilio">
                          <Row>
                            <span className="par-auxilio__nome">{a.municipio}</span>
                            <span className="t-data">{a.score?.toFixed(1) ?? '—'}</span>
                          </Row>
                          <p className="t-note">{a.motivos.join(' · ')}</p>
                          <p className="t-small">
                            vizinhos:{' '}
                            {a.vizinhos_com_folga
                              .map((v) => `${v.municipio} (${v.km.toFixed(0)} km)`)
                              .join(', ')}
                          </p>
                        </div>
                      ))}
                    </Stack>
                  )}
                </Section>
              </>
            )}

            <Section title="O que este mapa nao mostra">
              <Panel tone="verdict">
                <ul className="lista-marcas" data-tom="alerta">
                  {recursos.data.resumo.ressalvas.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
                {pessoal.data?.resumo.limites.map((l) => (
                  <p key={l} className="t-note">
                    {l}
                  </p>
                ))}
                {Object.keys(recursos.data.resumo.subtipos_moveis).length > 0 && (
                  <p className="t-note">
                    Composicao declarada das unidades moveis do CNES:{' '}
                    {Object.entries(recursos.data.resumo.subtipos_moveis)
                      .map(([k, v]) => `${k.replace(/_/g, ' ')} ${v}`)
                      .join(' · ')}
                    . A classificacao por nome e heuristica, nao cadastro.
                  </p>
                )}
              </Panel>
            </Section>
          </>
        )}
      </QueryState>
    </View>
  );
}
