import { useMemo, useState } from 'react';
import type { CSSProperties } from 'react';
import { assetUrl } from '../api/client';
import { useAguasMeta, useCruzamentoAguas, useMalhaMunicipal, useMunicipalRisk } from '../api/hooks';
import type { Cenario, CenarioSpec, ComponenteRisco, ModelCard, MunicipioRisco } from '../api/types';
import { CAMADAS, MapaMunicipal } from '../components/MapaMunicipal';
import type { Camada } from '../components/MapaMunicipal';
import { OutlookENSO } from '../components/OutlookENSO';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { QueryState } from '../components/QueryState';
import { DataTable, Empty, Grid, Panel, Row, Section, Stack, View } from '../components/ui';
import type { Column } from '../components/ui';
import { NIVEL, NIVEL_LABEL, sequencial } from '../theme/palette';
import './MunicipiosView.css';

/**
 * Rota `/municipios` — a unica visao da central com resolucao abaixo do estado.
 *
 * Pergunta que responde: "se eu tenho orcamento para agir em N municipios
 * antes da primavera, quais N, e por que cada um?"
 *
 * Pergunta que ela NAO responde, e a interface repete isso em tres lugares
 * (intro, faixa do modelo, painel de limites): onde vai encher. A ADR-013
 * fecha essa porta e ela continua fechada. O risco de uma tela municipal
 * bonita e exatamente comunicar a precisao que a cor sugere e o dado nao tem.
 */

const ROTULO_PERIGO: Record<string, string> = {
  oc_inundacao: 'inundacao (transbordo de rio)',
  oc_enchente_enxurrada: 'enchente / enxurrada',
  oc_alagamento: 'alagamento (drenagem urbana)',
  oc_solapamento_margem: 'solapamento de margem',
  oc_erosao: 'erosao',
};

const ROTULO_DANO: Record<string, string> = {
  dano_obitos: 'obitos',
  dano_desaparecidos: 'desaparecidos',
  dano_desabrigados: 'desabrigados / desalojados',
  dano_feridos: 'feridos',
  areas_ilhadas: 'areas ilhadas',
  dano_viario: 'danos a rodovias, pontes e ferrovias',
  dano_barragens: 'danos a barragens',
  risco_contaminacao_quimica: 'risco de contaminacao quimica',
};

const ROTULO_GRUPO: Record<string, string> = {
  exp_favelas: 'favelas e comunidades urbanas',
  exp_situacao_rua: 'populacao em situacao de rua',
  exp_comunidades_tradicionais: 'comunidades tradicionais (ribeirinhos, quilombolas, indigenas)',
  exp_deficiencia: 'pessoas com deficiencia',
};

/** Barra de componente: comprimento e a codificacao primaria, cor e reforco. */
function BarraComponente({
  label,
  comp,
  matiz,
}: {
  label: string;
  comp: ComponenteRisco;
  matiz: string;
}) {
  const ausente = comp.valor === null;
  return (
    <div className="comp">
      <Row>
        <span className="comp__label t-small">{label}</span>
        <span className="comp__valor t-data">{ausente ? '—' : comp.valor!.toFixed(2)}</span>
      </Row>
      <div
        className="comp__trilho"
        style={
          {
            '--comp-fracao': `${(comp.valor ?? 0) * 100}%`,
            '--comp-cor': sequencial(comp.valor ?? 0, matiz),
          } as CSSProperties
        }
        data-ausente={ausente ? 'sim' : undefined}
        role="presentation"
      />
      <Row>
        <ProvenanceBadge basis={comp.basis} />
        {ausente && comp.detalhe.motivo && <span className="t-note">{comp.detalhe.motivo}</span>}
      </Row>
    </div>
  );
}

/** Painel de drill-down: por que ESTE municipio esta nesta posicao. */
function DetalheMunicipio({ m, card }: { m: MunicipioRisco; card: ModelCard }) {
  const { impacto, deficit_prevencao: deficit, exposicao, perigo_sazonal, manutencao_ativos } = m.componentes;
  const perigos = impacto.detalhe.perigos ?? [];
  const danos = impacto.detalhe.danos ?? [];
  const lacunas = deficit.detalhe.lacunas ?? [];
  const grupos = exposicao.detalhe.grupos_expostos ?? [];

  return (
    <Panel
      title={m.municipio}
      actions={
        <span className="detalhe__score">
          <span className="t-hero">{m.score === null ? '—' : m.score.toFixed(1)}</span>
          <span
            className="detalhe__nivel t-small"
            style={{ '--nivel-cor': m.level ? NIVEL[m.level] : 'var(--bruma)' } as CSSProperties}
          >
            {m.level ? NIVEL_LABEL[m.level] : 'SEM BASE'}
          </span>
        </span>
      }
      footnote={`Populacao ${m.populacao?.toLocaleString('pt-BR') ?? '—'} · codigo IBGE ${m.cod_mun} · ${card.formula}`}
    >
      {m.completude === 'insuficiente' && (
        <Empty>
          Este municipio nao respondeu ao suplemento do MUNIC 2024 em grau suficiente para o indice.
          Ele aparece no mapa hachurado e fora do ranking — nao responder nao pode escondê-lo, mas
          tambem nao pode promove-lo.
        </Empty>
      )}

      <Grid min={230}>
        <BarraComponente label="Impacto hidrico 2024" comp={impacto} matiz={NIVEL.high} />
        <BarraComponente label="Deficit de prevencao" comp={deficit} matiz={NIVEL.elevated} />
        <BarraComponente label="Exposicao" comp={exposicao} matiz={NIVEL.low} />
        <BarraComponente label="Perigo sazonal (estadual)" comp={perigo_sazonal} matiz={NIVEL.moderate} />
      </Grid>

      {perigos.length > 0 && (
        <Section title="Perigos hidricos observados em 2024" rule={false}>
          <ul className="lista-marcas">
            {perigos.map((p) => (
              <li key={p}>{ROTULO_PERIGO[p] ?? p}</li>
            ))}
          </ul>
        </Section>
      )}

      {danos.length > 0 && (
        <Section title="Danos registrados" rule={false}>
          <ul className="lista-marcas">
            {danos.map((d) => (
              <li key={d} data-grave={d === 'dano_obitos' || d === 'dano_desaparecidos' ? 'sim' : undefined}>
                {ROTULO_DANO[d] ?? d}
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="Onde a prevencao falhou" rule={false}>
        {lacunas.length === 0 ? (
          <p className="t-small">
            {deficit.valor === null
              ? 'Sem resposta sobre plano de contingencia nem alerta.'
              : 'Plano de contingencia existia, foi executado e o alerta alcancou a populacao. Nenhuma lacuna declarada.'}
          </p>
        ) : (
          <ul className="lista-marcas" data-tom="alerta">
            {lacunas.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        )}
      </Section>

      {grupos.length > 0 && (
        <Section title="Grupos em maior risco declarados" rule={false}>
          <ul className="lista-marcas">
            {grupos.map((g) => (
              <li key={g}>{ROTULO_GRUPO[g] ?? g}</li>
            ))}
          </ul>
        </Section>
      )}

      {m.aguas && (
        <Section
          title="Memoria hidrica — JRC 1984-2021"
          note="Fora do indice: agua sazonal de satelite nao separa banhado de arroz irrigado."
          rule={false}
        >
          <div className="aguas-linhas">
            {(
              [
                ['permanente', 'agua permanente hoje'],
                ['sazonal', 'sazonal (varzea, banhado)'],
                ['perdida', 'PERDIDA — era agua e secou'],
                ['efemera', 'efemera — encheu uma vez'],
              ] as const
            ).map(([k, rotulo]) => (
              <div key={k} className="aguas-linha">
                <span className="aguas-linha__cor" style={{ background: CORES_AGUA.find((c) => c.id === k)!.css }} />
                <span className="t-small">{rotulo}</span>
                <span className="t-data">{m.aguas![k].km2?.toFixed(1) ?? '—'} km²</span>
                <span className="t-note">
                  {m.aguas![k].frac === null ? '—' : `${(m.aguas![k].frac! * 100).toFixed(1)}%`}
                </span>
              </div>
            ))}
          </div>
          <p className="aguas-destaque t-small">
            <strong>
              {m.aguas.memoria_hidrica_frac === null
                ? '—'
                : `${(m.aguas.memoria_hidrica_frac * 100).toFixed(1)}%`}
            </strong>{' '}
            do territorio ja foi agua entre 1984 e 2021 e hoje nao e —{' '}
            {m.aguas.memoria_hidrica_km2.toFixed(1)} km². A serie do JRC termina em 2021 e nao
            conhece a cheia de 2024.
          </p>
        </Section>
      )}

      {/* A lacuna aparece SEMPRE, inclusive nos municipios sem nenhum problema
          declarado: e a divida estrutural do indice, nao um detalhe do caso. */}
      <Section title="O que este indice nao ve" rule={false}>
        <p className="t-note">{manutencao_ativos.detalhe.motivo}</p>
      </Section>
    </Panel>
  );
}

/**
 * Seletor de horizonte. Os tres cenarios nao sao "graus de pessimismo": sao
 * tres perguntas diferentes, e o rotulo tem de dizer isso. `estrutural` e o
 * unico defensavel para 2027 — nao porque seja conservador, mas porque nao
 * depende de uma previsao ENSO que a 14 meses ninguem tem.
 */
const CENARIOS: { id: Cenario; label: string; sub: string }[] = [
  { id: 'atual', label: 'Agora', sub: 'ONI medido' },
  { id: 'ond2026', label: 'OND 2026', sub: 'outlook CPC' },
  { id: 'estrutural', label: '2027 +', sub: 'estrutural' },
];

/**
 * O overlay vem da API em modo vivo e do snapshot em modo estatico —
 * `assetUrl` resolve os dois e cobre tambem o subcaminho do GitHub Pages.
 * Nunca URL absoluta com porta fixa: quebraria fora desta maquina.
 */
const PNG_AGUAS = assetUrl('/geo/aguas.png');

export function MunicipiosView() {
  const [cenario, setCenario] = useState<Cenario>('atual');
  const risco = useMunicipalRisk(cenario);
  const malha = useMalhaMunicipal();
  const aguasMeta = useAguasMeta();
  const cruzamento = useCruzamentoAguas();
  const [camada, setCamada] = useState<Camada>('risco');
  const [selecionado, setSelecionado] = useState<number | null>(null);

  const municipios = useMemo(() => risco.data?.municipios ?? [], [risco.data]);
  const selecionadoObj = useMemo(
    () => municipios.find((m) => m.cod_mun === selecionado) ?? null,
    [municipios, selecionado],
  );

  const semPlano = useMemo(
    () => municipios.filter((m) => m.componentes.deficit_prevencao.detalhe.plano_contingencia === false),
    [municipios],
  );
  const planoNaoExecutado = useMemo(
    () =>
      municipios.filter(
        (m) =>
          m.componentes.deficit_prevencao.detalhe.plano_contingencia === true &&
          m.componentes.deficit_prevencao.detalhe.plano_executado === false,
      ),
    [municipios],
  );
  const comObitos = useMemo(
    () => municipios.filter((m) => (m.componentes.impacto.detalhe.danos ?? []).includes('dano_obitos')),
    [municipios],
  );

  const colunas: Column<MunicipioRisco>[] = [
    {
      key: 'municipio',
      header: 'Municipio',
      cell: (m) => m.municipio,
      sortValue: (m) => m.municipio,
    },
    {
      key: 'score',
      header: 'Indice',
      align: 'num',
      cell: (m) => (m.score === null ? '—' : m.score.toFixed(1)),
      // Ausente vai para o fim em qualquer direcao de ordenacao: um "—" no
      // topo do ranking seria lido como prioridade maxima.
      sortValue: (m) => (m.score === null ? -1 : m.score),
    },
    {
      key: 'level',
      header: 'Nivel',
      cell: (m) =>
        m.level ? (
          <span
            className="nivel-chip"
            style={{ '--nivel-cor': NIVEL[m.level] } as CSSProperties}
          >
            {NIVEL_LABEL[m.level]}
          </span>
        ) : (
          <span className="t-note">sem base</span>
        ),
      sortValue: (m) => m.score ?? -1,
    },
    {
      key: 'impacto',
      header: 'Impacto',
      align: 'num',
      cell: (m) => m.componentes.impacto.valor?.toFixed(2) ?? '—',
      sortValue: (m) => m.componentes.impacto.valor ?? -1,
    },
    {
      key: 'deficit',
      header: 'Deficit prev.',
      align: 'num',
      cell: (m) => m.componentes.deficit_prevencao.valor?.toFixed(2) ?? '—',
      sortValue: (m) => m.componentes.deficit_prevencao.valor ?? -1,
    },
    {
      key: 'pop',
      header: 'Populacao',
      align: 'num',
      cell: (m) => m.populacao?.toLocaleString('pt-BR') ?? '—',
      sortValue: (m) => m.populacao ?? -1,
    },
  ];

  return (
    <View
      title="Municipios"
      intro="Prioridade preventiva nos 497 municipios do RS: onde a proxima tempestade encontra a pior combinacao de impacto ja observado, deficit de prevencao e exposicao."
      actions={
        <div className="camadas" role="group" aria-label="camada do mapa">
          {CAMADAS.map((c) => (
            <button
              key={c.id}
              type="button"
              title={c.hint}
              className={`camadas__btn${camada === c.id ? ' camadas__btn--ativo' : ''}`}
              onClick={() => setCamada(c.id)}
              aria-pressed={camada === c.id}
            >
              {c.label}
            </button>
          ))}
        </div>
      }
    >
      {/* Faixa fixa, acima de qualquer numero. Uma tela municipal colorida
          comunica precisao de bairro; esta linha e o contrapeso e por isso
          nao e um rodape. */}
      <p className="aviso-escopo t-note">
        Isto NAO e previsao de cheia. Nenhuma camada desta engine antecipa evento individual
        (ADR-013). O indice ordena prioridade de acao preventiva a partir do que ja foi observado
        e do que a propria prefeitura declarou ao IBGE — o poligono inteiro recebe um valor, sem
        resolucao de bairro.
      </p>

      <Section
        title="Horizonte"
        note="Tres perguntas diferentes, nao tres graus de pessimismo. O que muda entre elas e a natureza da evidencia, nao o humor."
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
                {c.label} <span className="camadas__sub">{c.sub}</span>
              </button>
            ))}
          </div>
        }
      >
        <Grid min={380}>
          <OutlookENSO />
          {risco.data && <CenarioAtivo spec={risco.data.cenario_spec} cenario={risco.data.cenario} />}
        </Grid>
      </Section>

      <QueryState isLoading={risco.isLoading || malha.isLoading} isError={risco.isError || malha.isError}>
        {risco.data && malha.data && (
          <>
            <Section
              title={`Mapa — ${CAMADAS.find((c) => c.id === camada)!.label}`}
              note={`${risco.data.n_completo} municipios com base completa · ${risco.data.n_parcial} parcial · ${risco.data.n_insuficiente} sem base suficiente · fonte: ${risco.data.as_of_source}`}
            >
              <Grid min={420}>
                <Panel pad="tight">
                  <MapaMunicipal
                    malha={malha.data}
                    municipios={municipios}
                    camada={camada}
                    selecionado={selecionado}
                    onSelecionar={setSelecionado}
                    aguas={
                      camada === 'aguas' && aguasMeta.data?.disponivel && aguasMeta.data.overlay
                        ? { url: PNG_AGUAS, bbox: aguasMeta.data.overlay.bbox }
                        : null
                    }
                  />
                  <Legenda camada={camada} />
                </Panel>
                {selecionadoObj ? (
                  <DetalheMunicipio m={selecionadoObj} card={risco.data.model_card} />
                ) : (
                  <Panel title="Selecione um municipio">
                    <Empty>
                      Clique num poligono do mapa para ver a decomposicao do indice: quais perigos
                      hidricos ocorreram em 2024, quais danos, e onde exatamente a prevencao falhou.
                    </Empty>
                    <Stack gap={2}>
                      <Resumo n={semPlano.length} label="municipios sem plano de contingencia" />
                      <Resumo n={planoNaoExecutado.length} label="tinham plano e nao o executaram" />
                      <Resumo n={comObitos.length} label="registraram obitos no evento de 2024" />
                    </Stack>
                  </Panel>
                )}
              </Grid>
            </Section>

            <Section
              title="Ranking de prioridade preventiva"
              note="Ordenavel por qualquer coluna. Municipio sem base suficiente aparece no fim com '—', nunca com zero."
            >
              <DataTable
                columns={colunas}
                rows={municipios}
                rowKey={(m) => m.cod_mun}
                defaultSort={{ key: 'score', dir: 'desc' }}
              />
            </Section>

            <Section
              title="Onde a agua voltou"
              note={cruzamento.data?.independencia}
            >
              {cruzamento.data ? (
                <>
                  <p className="t-small">
                    <strong>{cruzamento.data.n_com_memoria_e_inundacao}</strong> municipios tem
                    terreno que ja foi agua entre 1984 e 2021 <em>e</em> declararam inundacao,
                    enxurrada ou alagamento ao IBGE em 2024. Ordenados pela fracao do territorio
                    com precedente de agua.
                  </p>
                  <DataTable
                    columns={[
                      {
                        key: 'municipio',
                        header: 'Municipio',
                        cell: (c) => c.municipio,
                        sortValue: (c) => c.municipio,
                      },
                      {
                        key: 'mem',
                        header: '% ja foi agua',
                        align: 'num',
                        cell: (c) =>
                          c.memoria_hidrica_frac === null
                            ? '—'
                            : `${(c.memoria_hidrica_frac * 100).toFixed(1)}%`,
                        sortValue: (c) => c.memoria_hidrica_frac ?? -1,
                      },
                      {
                        key: 'perdida',
                        header: 'Agua perdida',
                        align: 'num',
                        cell: (c) => (c.agua_perdida_km2 === null ? '—' : `${c.agua_perdida_km2.toFixed(1)} km²`),
                        sortValue: (c) => c.agua_perdida_km2 ?? -1,
                      },
                      {
                        key: 'perigos',
                        header: 'Perigos hidricos 2024',
                        cell: (c) => c.perigos_2024.map((p) => ROTULO_PERIGO[p] ?? p).join(', '),
                      },
                      {
                        key: 'score',
                        header: 'Indice',
                        align: 'num',
                        cell: (c) => c.score?.toFixed(1) ?? '—',
                        sortValue: (c) => c.score ?? -1,
                      },
                    ]}
                    rows={cruzamento.data.municipios}
                    rowKey={(c) => c.cod_mun}
                  />
                </>
              ) : (
                <Empty>Cruzamento indisponivel — a camada de agua nao foi calculada.</Empty>
              )}
            </Section>

            <Section title="Ficha do modelo">
              <Grid min={300}>
                <Panel title="Formula e pesos" tone="verdict">
                  <p className="t-data">{risco.data.model_card.formula}</p>
                  <ul className="lista-marcas">
                    {Object.entries(risco.data.model_card.componentes).map(([k, v]) => (
                      <li key={k}>
                        <strong className="mono">{k}</strong> — {v}
                      </li>
                    ))}
                  </ul>
                  <p className="t-note">
                    Pesos: {Object.entries(risco.data.model_card.pesos).map(([k, v]) => `${k} ${v}`).join(' · ')}.
                    Cortes: {Object.entries(risco.data.model_card.cortes).map(([k, v]) => `${k} ≥ ${v}`).join(' · ')}.
                    Sao escolha editorial declarada, nunca calibrada contra desfecho.
                  </p>
                </Panel>
                <Panel title="Limites" tone="verdict">
                  <ul className="lista-marcas" data-tom="alerta">
                    {risco.data.model_card.limites.map((l) => (
                      <li key={l}>{l}</li>
                    ))}
                  </ul>
                </Panel>
              </Grid>
            </Section>
          </>
        )}
      </QueryState>
    </View>
  );
}

/**
 * O que o cenario escolhido faz com o indice. Existe porque o multiplicador
 * e invisivel no numero final: sem este painel, trocar de horizonte muda 497
 * numeros sem que nada na tela explique por que.
 */
function CenarioAtivo({ spec, cenario }: { spec: CenarioSpec; cenario: Cenario }) {
  const estrutural = cenario === 'estrutural';
  return (
    <Panel
      title={spec.label}
      actions={<ProvenanceBadge basis={estrutural ? 'measured' : spec.basis} />}
      footnote={`Fonte do componente sazonal: ${spec.fonte} · horizonte ${spec.horizonte}`}
    >
      <Row>
        <span className="t-small">Multiplicador sazonal aplicado</span>
        <span className="t-hero">{estrutural ? '—' : spec.multiplicador.toFixed(2)}</span>
      </Row>
      <p className="t-small">{spec.h_rotulo}</p>

      {/* Sem esta linha, dois cenarios com numeros identicos parecem bug. */}
      {spec.leitura_saturacao && (
        <p className="cenario__saturacao t-small">{spec.leitura_saturacao}</p>
      )}

      <p className="t-note">{spec.nota}</p>
    </Panel>
  );
}

function Resumo({ n, label }: { n: number; label: string }) {
  return (
    <p className="resumo">
      <span className="t-hero resumo__n">{n}</span>
      <span className="t-small">{label}</span>
    </p>
  );
}

/**
 * Legenda. Muda de gramatica junto com o mapa: degraus rotulados para a
 * camada ordinal, rampa continua para as sequenciais. Uma legenda que nao
 * acompanha a escala e pior que nenhuma.
 */
/** Cores do overlay do JRC — espelham CORES_RGBA de src/risk/aguas.py. */
const CORES_AGUA: { id: string; label: string; css: string }[] = [
  { id: 'permanente', label: 'agua permanente (rio, lago)', css: 'rgb(43,143,214)' },
  { id: 'sazonal', label: 'sazonal (varzea, banhado, arroz)', css: 'rgb(94,190,214)' },
  { id: 'perdida', label: 'PERDIDA — era agua e secou', css: 'rgb(193,133,58)' },
  { id: 'efemera', label: 'efemera — encheu uma vez', css: 'rgb(154,108,74)' },
];

function Legenda({ camada }: { camada: Camada }) {
  if (camada === 'aguas') {
    return (
      <div className="legenda">
        {CORES_AGUA.map((c) => (
          <span key={c.id} className="legenda__item t-note">
            <span className="legenda__amostra" style={{ background: c.css }} />
            {c.label}
          </span>
        ))}
      </div>
    );
  }
  if (camada === 'risco') {
    return (
      <div className="legenda">
        {(Object.keys(NIVEL) as (keyof typeof NIVEL)[]).map((k) => (
          <span key={k} className="legenda__item t-note">
            <span className="legenda__amostra" style={{ background: NIVEL[k] }} />
            {NIVEL_LABEL[k]}
          </span>
        ))}
        <span className="legenda__item t-note">
          <span className="legenda__amostra legenda__amostra--hachura" />
          sem base
        </span>
      </div>
    );
  }
  const matiz = camada === 'deficit' ? NIVEL.elevated : camada === 'impacto' ? NIVEL.high : NIVEL.low;
  return (
    <div className="legenda">
      <span className="t-note">0</span>
      <span
        className="legenda__rampa"
        style={{
          background: `linear-gradient(90deg, ${sequencial(0, matiz)}, ${sequencial(0.5, matiz)}, ${sequencial(1, matiz)})`,
        }}
      />
      <span className="t-note">1</span>
      <span className="legenda__item t-note">
        <span className="legenda__amostra legenda__amostra--hachura" />
        sem base
      </span>
    </div>
  );
}
