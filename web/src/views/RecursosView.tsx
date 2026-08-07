import { useMemo, useState } from 'react';
import { useMalhaMunicipal, useMunicipalRisk, useRecursos } from '../api/hooks';
import { MapaMunicipal } from '../components/MapaMunicipal';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { QueryState } from '../components/QueryState';
import { DataTable, Empty, Grid, Panel, Row, Section, Stack, View } from '../components/ui';
import type { Column } from '../components/ui';
import { CATEGORICO, ESTADO } from '../theme/palette';
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

/** Cor por papel. Categorico = identidade, nao magnitude (DESIGN.md §1). */
const CORES: Record<string, string> = {
  fixo_hospitalar: CATEGORICO[0],
  fixo_urgencia: CATEGORICO[1],
  psicossocial: CATEGORICO[3],
  bombeiro: CATEGORICO[2],
  policia: CATEGORICO[5],
  movel: CATEGORICO[4],
  regulacao: ESTADO.ok,
};

const ORDEM_PAPEL = [
  'fixo_hospitalar',
  'fixo_urgencia',
  'regulacao',
  'movel',
  'psicossocial',
  'bombeiro',
  'policia',
];

export function RecursosView() {
  const recursos = useRecursos();
  const malha = useMalhaMunicipal();
  const risco = useMunicipalRisk('atual');
  const [visiveis, setVisiveis] = useState<Set<string>>(new Set(ORDEM_PAPEL));

  const pontosFiltrados = useMemo(
    () => (recursos.data?.pontos ?? []).filter((p) => visiveis.has(p.papel)),
    [recursos.data, visiveis],
  );

  const alternar = (papel: string) =>
    setVisiveis((s) => {
      const n = new Set(s);
      if (n.has(papel)) n.delete(papel);
      else n.add(papel);
      return n;
    });

  const colunasVazio: Column<NonNullable<typeof recursos.data>['vazios'][number]>[] = [
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
                <div className="recursos-legenda">
                  {ORDEM_PAPEL.map((papel) => {
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
                        <span className="recursos-legenda__marca" style={{ background: CORES[papel] }} />
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
              {recursos.data.vazios.length === 0 ? (
                <Empty>Nenhum municipio avaliado combina risco e vazio critico.</Empty>
              ) : (
                <DataTable
                  columns={colunasVazio}
                  rows={recursos.data.vazios}
                  rowKey={(v) => v.cod_mun}
                />
              )}
            </Section>

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

            <Section title="O que este mapa nao mostra">
              <Panel tone="verdict">
                <ul className="lista-marcas" data-tom="alerta">
                  {recursos.data.resumo.ressalvas.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
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
