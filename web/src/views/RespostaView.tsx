import { useMemo, useState } from 'react';
import type { CSSProperties } from 'react';
import { useResposta } from '../api/hooks';
import type { MunicipioResposta } from '../api/types';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { QueryState } from '../components/QueryState';
import { DataTable, Empty, Grid, Panel, Row, Section, Stack, View } from '../components/ui';
import type { Column } from '../components/ui';
import { ESTADO, sequencial } from '../theme/palette';
import './RespostaView.css';

/**
 * Rota `/resposta` — o DEPOIS do evento.
 *
 * O indice municipal responde "onde agir antes". Esta visao responde as
 * perguntas seguintes: quem estava exposto, se a saude aguentou, se ha para
 * onde levar, por quantos dias o municipio se sustentou e o que conseguiu
 * entregar.
 *
 * Duas regras de desenho, ambas herdadas do resto do projeto:
 *
 * 1. A palavra LEITO nao aparece em lugar nenhum. O dado e estabelecimento, e
 *    a razao entre um e outro varia de 10 a 400 conforme o porte. O card de
 *    capacidade repete a unidade ao lado do numero.
 * 2. As lacunas (dias letivos, recuperacao financeira, alcance do apoio
 *    psicologico) ganham um painel PROPRIO, do mesmo tamanho dos outros — nao
 *    uma nota de rodape. Sao a maior parte do que falta para responder
 *    "recuperacao", e escondê-las faria a tela parecer completa.
 */

export function RespostaView() {
  const { data, isLoading, isError } = useResposta();
  const [selecionado, setSelecionado] = useState<number | null>(null);

  const municipios = useMemo(() => data?.municipios ?? [], [data]);
  const escolhido = useMemo(
    () => municipios.find((m) => m.cod_mun === selecionado) ?? null,
    [municipios, selecionado],
  );

  const colunas: Column<MunicipioResposta>[] = [
    { key: 'municipio', header: 'Municipio', cell: (m) => m.municipio, sortValue: (m) => m.municipio },
    {
      key: 'unid',
      header: 'Unidades',
      align: 'num',
      cell: (m) => (m.capacidade.total === 0 ? '—' : m.capacidade.total),
      sortValue: (m) => m.capacidade.total,
    },
    {
      key: 'km',
      header: 'km ate a mais proxima',
      align: 'num',
      cell: (m) =>
        m.capacidade.km_ate_unidade_mais_proxima === null
          ? 'tem no municipio'
          : `${m.capacidade.km_ate_unidade_mais_proxima.toFixed(1)}`,
      sortValue: (m) => m.capacidade.km_ate_unidade_mais_proxima ?? -1,
    },
    {
      key: 'aut',
      header: 'Autonomia',
      align: 'num',
      cell: (m) =>
        m.autonomia_logistica.indice === null ? '—' : m.autonomia_logistica.indice.toFixed(2),
      sortValue: (m) => m.autonomia_logistica.indice ?? 2, // ausente por ultimo
    },
    {
      key: 'psico',
      header: 'Apoio psicologico',
      cell: (m) =>
        m.resposta.apoio_psicologico === null ? (
          <span className="t-note">—</span>
        ) : m.resposta.apoio_psicologico ? (
          'ofereceu'
        ) : (
          <span className="marca-falta">nao ofereceu</span>
        ),
      sortValue: (m) => (m.resposta.apoio_psicologico === null ? 2 : m.resposta.apoio_psicologico ? 1 : 0),
    },
    {
      key: 'saude',
      header: 'Saude afetada',
      align: 'num',
      cell: (m) => (m.saude.impactos.length === 0 ? '—' : m.saude.impactos.length),
      sortValue: (m) => m.saude.impactos.length,
    },
    {
      key: 'vuln',
      header: 'Grupos atingidos',
      align: 'num',
      cell: (m) => (m.vulneraveis.grupos.length === 0 ? '—' : m.vulneraveis.grupos.length),
      sortValue: (m) => m.vulneraveis.grupos.length,
    },
  ];

  return (
    <View
      title="Resposta"
      intro="O depois do evento: quem estava exposto, se a saude aguentou, se ha para onde levar, por quantos dias o municipio se sustentou e o que conseguiu entregar."
    >
      <p className="aviso-escopo t-note">
        Estas variaveis descrevem consequencia e resposta, nao predisposicao — e por isso NAO entram
        no indice de prioridade preventiva. Soma-las transformaria a lista de &quot;onde agir
        antes&quot; num ranking de quem sofreu mais, que e outra pergunta.
      </p>

      <QueryState isLoading={isLoading} isError={isError}>
        {data && (
          <>
            <Section title="O estado em numeros">
              <Grid min={230}>
                <Cartao
                  n={data.resumo.capacidade.municipios_sem_unidade}
                  total={data.resumo.n_municipios}
                  label="municipios sem hospital nem pronto-socorro"
                  nota={
                    data.resumo.capacidade.km_mediano_ate_unidade
                      ? `mediana de ${data.resumo.capacidade.km_mediano_ate_unidade} km ate a unidade mais proxima`
                      : undefined
                  }
                  tom="falta"
                />
                <Cartao
                  n={data.resumo.saude_afetada}
                  total={data.resumo.n_municipios}
                  label="tiveram o sistema de saude afetado em 2024"
                  nota="estrutura, equipamento, atendimento suspenso ou remanejamento de pacientes"
                />
                <Cartao
                  n={data.resumo.apoio_psicologico.nao_ofereceram}
                  total={
                    data.resumo.apoio_psicologico.ofereceram + data.resumo.apoio_psicologico.nao_ofereceram
                  }
                  label="NAO ofereceram apoio psicologico as vitimas"
                  nota={`${data.resumo.apoio_psicologico.ofereceram} ofereceram`}
                  tom="falta"
                />
                <Cartao
                  n={data.resumo.capacidade.total_estabelecimentos}
                  label="estabelecimentos hospitalares e de urgencia no RS"
                  nota={data.resumo.capacidade.aviso}
                />
              </Grid>
            </Section>

            <Section
              title="Capacidade, autonomia e resposta por municipio"
              note="Clique numa linha para abrir a decomposicao. Ordenavel por qualquer coluna."
            >
              <Grid min={420}>
                <Panel pad="tight">
                  <DataTable
                    columns={colunas}
                    rows={municipios}
                    rowKey={(m) => m.cod_mun}
                    defaultSort={{ key: 'km', dir: 'desc' }}
                  />
                </Panel>
                {escolhido ? (
                  <Detalhe m={escolhido} />
                ) : (
                  <Panel title="Selecione um municipio">
                    <Empty>
                      A tabela ordena por distancia ate a unidade de urgencia mais proxima. Clique
                      numa linha para ver grupos atingidos, impacto na saude, as sete escalas de
                      autonomia logistica e o que foi entregue.
                    </Empty>
                  </Panel>
                )}
              </Grid>
              {/* Selecao por clique na linha: a DataTable nao expoe onRowClick,
                  entao o seletor fica aqui, explicito e acessivel por teclado. */}
              <Row>
                <label className="t-small seletor">
                  Municipio
                  <select
                    value={selecionado ?? ''}
                    onChange={(e) => setSelecionado(e.target.value ? Number(e.target.value) : null)}
                  >
                    <option value="">—</option>
                    {[...municipios]
                      .sort((a, b) => a.municipio.localeCompare(b.municipio))
                      .map((m) => (
                        <option key={m.cod_mun} value={m.cod_mun}>
                          {m.municipio}
                        </option>
                      ))}
                  </select>
                </label>
              </Row>
            </Section>

            {/* Painel proprio, do mesmo peso dos outros: as lacunas sao a maior
                parte do que falta para responder "recuperacao". */}
            <Section title="O que esta central ainda nao responde">
              <Grid min={280}>
                {data.lacunas.map((l) => (
                  <Panel key={l.id} title={l.titulo} tone="verdict">
                    <p className="t-small">{l.motivo}</p>
                    <ProvenanceBadge basis={null} />
                  </Panel>
                ))}
              </Grid>
            </Section>
          </>
        )}
      </QueryState>
    </View>
  );
}

function Cartao({
  n,
  total,
  label,
  nota,
  tom,
}: {
  n: number;
  total?: number;
  label: string;
  nota?: string;
  tom?: 'falta';
}) {
  return (
    <Panel>
      <p className="cartao">
        <span className="t-hero" data-tom={tom}>
          {n.toLocaleString('pt-BR')}
        </span>
        {total !== undefined && <span className="t-note">de {total}</span>}
      </p>
      <p className="t-small cartao__label">{label}</p>
      {nota && <p className="t-note">{nota}</p>}
    </Panel>
  );
}

function Detalhe({ m }: { m: MunicipioResposta }) {
  const cap = m.capacidade;
  return (
    <Panel
      title={m.municipio}
      actions={<ProvenanceBadge basis="measured" />}
      footnote={`Populacao ${m.populacao?.toLocaleString('pt-BR') ?? '—'} · codigo IBGE ${m.cod_mun}`}
    >
      <Section title="Capacidade instalada" rule={false}>
        {cap.total === 0 ? (
          <p className="t-small">
            <strong className="marca-falta">Nenhum hospital ou pronto-socorro no municipio.</strong>{' '}
            A unidade mais proxima esta a{' '}
            <strong>{cap.km_ate_unidade_mais_proxima?.toFixed(1) ?? '—'} km</strong> em linha reta —
            distancia por estrada e maior, e em cheia pode nao existir.
          </p>
        ) : (
          <ul className="lista-marcas">
            <li>
              {cap.total} {cap.unidade} ({cap.hospitais} hospitalar
              {cap.hospitais === 1 ? '' : 'es'}, {cap.urgencia} de urgencia)
            </li>
            <li>{cap.centro_cirurgico} com centro cirurgico · {cap.centro_obstetrico} com centro obstetrico</li>
            {cap.por_100k !== null && <li>{cap.por_100k.toFixed(2)} por 100 mil habitantes</li>}
          </ul>
        )}
        <p className="t-note">
          Unidade: <strong>{cap.unidade}</strong>, nunca leitos — a razao entre os dois varia de 10 a
          400 conforme o porte.
        </p>
      </Section>

      <Section title="Autonomia logistica" rule={false}>
        {m.autonomia_logistica.indice === null ? (
          <Empty>Nenhuma das sete escalas foi aplicavel — o municipio nao relatou ter sido testado.</Empty>
        ) : (
          <>
            <Row>
              <span className="t-small">indice ({m.autonomia_logistica.n_aplicaveis} de 7 escalas)</span>
              <span className="t-hero">{m.autonomia_logistica.indice.toFixed(2)}</span>
            </Row>
            <div className="escalas">
              {m.autonomia_logistica.itens.map((it) => (
                <div key={it.id} className="escala" data-na={it.aplicavel ? undefined : 'sim'}>
                  <span className="t-small">{it.rotulo}</span>
                  <span
                    className="escala__barra"
                    style={
                      {
                        '--escala-frac': `${(it.valor ?? 0) * 100}%`,
                        // ESTADO.ok (situacao), nao NIVEL (risco): a barra mede
                        // desempenho da resposta, nao gravidade do perigo.
                        '--escala-cor': sequencial(it.valor ?? 0, ESTADO.ok),
                      } as CSSProperties
                    }
                  />
                  <span className="t-note escala__resposta">{it.resposta ?? '—'}</span>
                </div>
              ))}
            </div>
            <p className="t-note">
              &quot;Nao houve/nao necessitou&quot; conta como NAO APLICAVEL, nunca como nota maxima:
              nao precisar de resgate nao demonstra capacidade de resgate.
            </p>
          </>
        )}
      </Section>

      <Section title="Grupos atingidos declarados" rule={false}>
        {m.vulneraveis.grupos.length === 0 ? (
          <p className="t-small">Nenhum grupo declarado ({m.vulneraveis.n_respondidos} perguntas respondidas).</p>
        ) : (
          <ul className="lista-marcas" data-tom="alerta">
            {m.vulneraveis.grupos.map((g) => (
              <li key={g}>{g}</li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Impacto no sistema de saude" rule={false}>
        {m.saude.impactos.length === 0 ? (
          <p className="t-small">Nenhum impacto declarado.</p>
        ) : (
          <ul className="lista-marcas" data-tom="alerta">
            {m.saude.impactos.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Resposta prestada" rule={false}>
        <Stack gap={2}>
          <p className="t-small">
            Apoio psicologico:{' '}
            {m.resposta.apoio_psicologico === null ? (
              <span className="t-note">nao informado</span>
            ) : m.resposta.apoio_psicologico ? (
              <strong>ofereceu</strong>
            ) : (
              <strong className="marca-falta">nao ofereceu</strong>
            )}
          </p>
          {m.resposta.prestadas.length === 0 ? (
            <p className="t-small">Nenhuma acao de resposta declarada.</p>
          ) : (
            <ul className="lista-marcas">
              {m.resposta.prestadas.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          )}
        </Stack>
      </Section>
    </Panel>
  );
}
