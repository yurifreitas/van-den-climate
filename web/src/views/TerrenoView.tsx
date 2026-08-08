import { useMemo, useState } from 'react';
import { useTerreno } from '../api/hooks';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { QueryState } from '../components/QueryState';
import { DataTable, Empty, Grid, Panel, Row, Section, Stack, View } from '../components/ui';
import type { Column } from '../components/ui';
import type { MunicipioDegradacao, MunicipioHidrologia } from '../api/types';
import './TerrenoView.css';

/**
 * Rota `/terreno` — no que a chuva cai.
 *
 * A tela responde a pergunta que faltava entre "vai chover" e "vai alagar":
 * dos 100 mm que caem, quantos infiltram. E responde com o que o mapa
 * sustenta — solo, cobertura e relevo do IBGE a 1:250.000 — nunca com mais
 * resolucao do que isso.
 *
 * TRES DECISOES DE INTERFACE, todas sobre o que NAO mostrar:
 *
 * 1. O escoamento aparece sempre em PAR, seco e umido. Publicar so a condicao
 *    de umidade media descreveria um estado que quase nunca e o do desastre:
 *    a cheia acontece na terceira chuva, com o perfil ja cheio, e o salto
 *    entre as duas colunas e a informacao mais util da tabela.
 *
 * 2. A velocidade de resposta e rotulo, nao numero. Sem talvegue e sem
 *    declividade medida nao existe tempo de concentracao em minutos; imprimir
 *    "3,4 h" seria inventar precisao que nenhum insumo aqui tem.
 *
 * 3. Na erosao, a area medida vem ANTES do indice. Quem le de cima para baixo
 *    encontra primeiro "tantos km2 de lavoura em encosta", que e verificavel,
 *    e so entao o indice, que e tabela com P=1 e sem teto.
 */

/** Rotulo curto por classe de cobertura, na ordem em que domina o estado. */
const COBERTURA_LABEL: Record<string, string> = {
  agropecuaria: 'mosaico agropecuario',
  agricultura: 'lavoura',
  pastagem: 'pastagem',
  campo_nativo: 'campo nativo',
  vegetacao_secundaria: 'vegetacao secundaria',
  floresta_nativa: 'floresta nativa',
  silvicultura: 'silvicultura',
  banhado: 'banhado',
  urbano: 'area urbana',
  agua: 'agua',
  dunas: 'dunas',
};

function pct(v: number | null | undefined): string {
  return v === null || v === undefined ? '—' : `${(v * 100).toFixed(0)}%`;
}

export function TerrenoView() {
  const terreno = useTerreno(120);
  const [aba, setAba] = useState<'escoamento' | 'erosao'>('escoamento');

  const colunasHidro: Column<MunicipioHidrologia>[] = useMemo(
    () => [
      {
        key: 'municipio',
        header: 'Municipio',
        cell: (m) => m.municipio,
        sortValue: (m) => m.municipio,
      },
      {
        key: 'cn',
        header: 'CN',
        align: 'num',
        cell: (m) => m.cn2.toFixed(0),
        sortValue: (m) => m.cn2,
      },
      {
        key: 'chuva',
        header: 'Chuva TR 10',
        align: 'num',
        cell: (m) => {
          const e = m.eventos.find((x) => x.tr_anos === 10);
          return e ? `${e.p24h_mm.toFixed(0)} mm` : '—';
        },
        sortValue: (m) => m.eventos.find((x) => x.tr_anos === 10)?.p24h_mm ?? -1,
      },
      {
        key: 'escoa',
        header: 'Escoa (seco / umido)',
        align: 'num',
        cell: (m) => {
          const e = m.eventos.find((x) => x.tr_anos === 10);
          if (!e) return '—';
          return (
            <span>
              {e.escoamento_mm.toFixed(0)}
              <span className="t-note"> / </span>
              <strong>{e.escoamento_mm_solo_umido.toFixed(0)}</strong>
              <span className="t-note"> mm</span>
            </span>
          );
        },
        sortValue: (m) => m.eventos.find((x) => x.tr_anos === 10)?.escoamento_mm ?? -1,
      },
      {
        key: 'resposta',
        header: 'Resposta',
        cell: (m) => <span className="t-note">{m.resposta ?? '—'}</span>,
        sortValue: (m) => m.resposta_escore ?? -1,
      },
      {
        key: 'cobertura',
        header: 'Cobertura dominante',
        cell: (m) => {
          const [chave, valor] = Object.entries(m.cobertura)[0] ?? [];
          return chave ? `${COBERTURA_LABEL[chave] ?? chave} ${pct(valor)}` : '—';
        },
      },
    ],
    [],
  );

  const colunasDegr: Column<MunicipioDegradacao>[] = useMemo(
    () => [
      {
        key: 'municipio',
        header: 'Municipio',
        cell: (m) => m.municipio,
        sortValue: (m) => m.municipio,
      },
      {
        key: 'declive',
        header: 'Uso intensivo em declive',
        align: 'num',
        cell: (m) => `${m.km2_uso_intensivo_em_declive.toFixed(0)} km2`,
        sortValue: (m) => m.km2_uso_intensivo_em_declive,
      },
      {
        key: 'raso',
        header: 'Solo raso sob lavoura',
        align: 'num',
        cell: (m) =>
          m.km2_solo_raso_sob_uso_intensivo > 0
            ? `${m.km2_solo_raso_sob_uso_intensivo.toFixed(0)} km2`
            : '—',
        sortValue: (m) => m.km2_solo_raso_sob_uso_intensivo,
      },
      {
        key: 'indice',
        header: 'Indice (posicao no RS)',
        align: 'num',
        cell: (m) => (
          <span>
            {m.indice_rusle_t_ha_ano.toFixed(0)}
            <span className="t-note"> · {m.classe}</span>
          </span>
        ),
        sortValue: (m) => m.indice_rusle_t_ha_ano,
      },
    ],
    [],
  );

  return (
    <View
      title="Terreno"
      intro="No que a chuva cai. Solo, cobertura e relevo decidem quanto de uma chuva infiltra e quanto vira enxurrada — e quanto de solo ela leva junto."
    >
      <QueryState isLoading={terreno.isLoading} isError={terreno.isError}>
        {terreno.data && (
          <Stack gap={4}>
            <Row>
              <ProvenanceBadge basis={terreno.data.provenance.basis} />
              <span className="footnote">
                Tudo aqui e traduzido: a fracao de solo e de cobertura por baixo e medida
                (IBGE/BDiA 1:250.000), mas grupo hidrologico, Curve Number e chuva de projeto
                sao tabela e ajuste. Nenhum numero desta tela foi confrontado com vazao
                observada.
              </span>
            </Row>

            <Section
              title="O estado em quatro numeros"
              note={`Curve Number mediano ${terreno.data.hidrologia.resumo.cn2_mediano ?? '—'}; perda inicial Ia = ${terreno.data.hidrologia.resumo.razao_ia} S.`}
            >
              <Grid min={230}>
                <Panel title="CN mediano do RS">
                  <span className="t-hero">{terreno.data.hidrologia.resumo.cn2_mediano ?? '—'}</span>
                  <p className="footnote">
                    Quanto maior, menos infiltra. Latossolo profundo do planalto fica perto de
                    50; encosta de basalto raso passa de 85.
                  </p>
                </Panel>
                <Panel title="Uso intensivo em declive">
                  <span className="t-hero">
                    {terreno.data.degradacao.resumo.km2_uso_intensivo_em_declive_rs.toFixed(0)}
                  </span>
                  <p className="footnote">
                    km2 de lavoura ou mosaico agropecuario em relevo ondulado ou mais. Numero
                    medido, cruzando duas classes do IBGE — nao passa por tabela nenhuma.
                  </p>
                </Panel>
                <Panel title="Solo raso sob lavoura">
                  <span className="t-hero">
                    {terreno.data.degradacao.resumo.km2_solo_raso_sob_uso_intensivo_rs.toFixed(0)}
                  </span>
                  <p className="footnote">
                    km2 de Neossolo Litolico — poucos decimetros sobre rocha — sob uso
                    intensivo. Perda ali nao se recupera em escala humana.
                  </p>
                </Panel>
                <Panel title="Estacoes de chuva">
                  <span className="t-hero">{terreno.data.hidrologia.resumo.n_estacoes_chuva}</span>
                  <p className="footnote">
                    Series do GHCN com anos completos suficientes para ajustar Gumbel. Cada
                    municipio herda a estacao mais proxima do centroide, e a distancia viaja no
                    dado.
                  </p>
                </Panel>
              </Grid>
            </Section>

            <Section
              title="Onde as duas coisas acontecem juntas"
              note={terreno.data.concentracao.criterio}
            >
              {terreno.data.concentracao.municipios.length === 0 ? (
                <Empty>Nenhum municipio esta no decil superior das duas camadas.</Empty>
              ) : (
                <div className="terreno-concentracao">
                  {terreno.data.concentracao.municipios.map((m) => (
                    <article key={m.cod_mun} className="terreno-concentracao__item">
                      <h4>{m.municipio}</h4>
                      <p className="footnote">
                        CN {m.cn2.toFixed(0)} · indice de erosao {m.indice_rusle_t_ha_ano.toFixed(0)} ·
                        resposta {m.resposta ?? '—'}
                      </p>
                      <p className="footnote">
                        {m.km2_uso_intensivo_em_declive.toFixed(0)} km2 de uso intensivo em declive
                      </p>
                    </article>
                  ))}
                </div>
              )}
            </Section>

            <Section title="Por unidade de relevo" note="A bacia nao respeita divisa municipal; a unidade geomorfologica e a regiao natural mais proxima disso que o dado sustenta.">
              <Grid min={280}>
                {terreno.data.hidrologia.regioes.slice(0, 9).map((r) => (
                  <Panel key={r.unidade} title={r.unidade}>
                    <Row>
                      <span className="t-hero">{r.cn2_medio?.toFixed(0) ?? '—'}</span>
                      <span className="t-note">
                        {r.n_municipios} municipios · {r.area_km2.toFixed(0)} km2
                      </span>
                    </Row>
                    {r.municipios_cn_alto.length > 0 && (
                      <p className="footnote">
                        decil superior aqui: {r.municipios_cn_alto.slice(0, 5).join(', ')}
                      </p>
                    )}
                  </Panel>
                ))}
              </Grid>
            </Section>

            <Section
              title="Municipio a municipio"
              note="Escoamento sempre em par: solo seco e solo ja encharcado. O segundo e o do desastre."
            >
              <Row>
                <button
                  type="button"
                  className={`terreno-aba ${aba === 'escoamento' ? 'terreno-aba--ativa' : ''}`}
                  onClick={() => setAba('escoamento')}
                >
                  Escoamento
                </button>
                <button
                  type="button"
                  className={`terreno-aba ${aba === 'erosao' ? 'terreno-aba--ativa' : ''}`}
                  onClick={() => setAba('erosao')}
                >
                  Erosao
                </button>
              </Row>
              {aba === 'escoamento' ? (
                <DataTable
                  columns={colunasHidro}
                  rows={terreno.data.hidrologia.municipios}
                  rowKey={(m) => m.cod_mun}
                />
              ) : (
                <>
                  <p className="footnote">{terreno.data.degradacao.resumo.nota_escala}</p>
                  <DataTable
                    columns={colunasDegr}
                    rows={terreno.data.degradacao.municipios}
                    rowKey={(m) => m.cod_mun}
                  />
                </>
              )}
              <p className="footnote">
                Mostrando {terreno.data.hidrologia.municipios.length} de{' '}
                {terreno.data.hidrologia.n_total} municipios.
              </p>
            </Section>

            <Section title="O que este modelo nao sabe">
              <ul className="terreno-limites">
                {[...terreno.data.hidrologia.limites, ...terreno.data.degradacao.limites].map(
                  (l) => (
                    <li key={l}>{l}</li>
                  ),
                )}
              </ul>
            </Section>
          </Stack>
        )}
      </QueryState>
    </View>
  );
}
