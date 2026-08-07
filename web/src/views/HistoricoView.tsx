import { useMemo } from 'react';
import type { CSSProperties } from 'react';
import { useHistorico } from '../api/hooks';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { QueryState } from '../components/QueryState';
import { DataTable, Empty, Grid, Panel, Row, Section, View } from '../components/ui';
import type { Column } from '../components/ui';
import { FRIO, GIZ, GRID, QUENTE, alpha, divergingValue } from '../theme/palette';
import './HistoricoView.css';

/**
 * Rota `/historico` — meio seculo de primaveras no RS.
 *
 * Responde a pergunta que a engine sempre afirmou e nunca tinha medido com o
 * proprio dado: **El Nino molha o Rio Grande do Sul?** E responde com o trio
 * da ADR-002 (frequencia de dias umidos, intensidade, p95 diario) calculado
 * sobre chuva observada, nao sobre literatura.
 *
 * A tela e organizada em torno do intervalo, nao da media. Um delta positivo
 * com IC que cruza zero e apresentado como cruzando zero, com o mesmo destaque
 * do que separa — porque a decisao que importa muda com isso, e a media
 * sozinha esconderia.
 */

const METRICAS = [
  { id: 'freq_dias_umidos', label: 'Frequencia de dias umidos', unidade: 'fracao', casas: 3 },
  { id: 'intensidade_mm', label: 'Intensidade em dia umido', unidade: 'mm/dia', casas: 2 },
  { id: 'p95_mm', label: 'p95 diario', unidade: 'mm', casas: 2 },
  { id: 'total_mm', label: 'Total da estacao', unidade: 'mm', casas: 1 },
] as const;

const COR_FASE: Record<string, string> = {
  'El Nino': QUENTE,
  Neutro: GRID,
  'La Nina': FRIO,
};

export function HistoricoView() {
  const { data, isLoading, isError } = useHistorico();

  const anos = useMemo(() => data?.por_ano ?? [], [data]);

  const colunas: Column<(typeof anos)[number]>[] = [
    { key: 'ano', header: 'Ano', align: 'num', cell: (a) => a.ano, sortValue: (a) => a.ano },
    {
      key: 'fase',
      header: 'Fase ENSO',
      cell: (a) => (
        <span className="fase-chip" style={{ '--fase-cor': COR_FASE[a.fase] ?? GIZ } as CSSProperties}>
          {a.fase}
        </span>
      ),
      sortValue: (a) => a.fase,
    },
    {
      key: 'oni',
      header: 'ONI OND',
      align: 'num',
      cell: (a) => (a.oni_ond === null ? '—' : a.oni_ond.toFixed(2)),
      sortValue: (a) => a.oni_ond ?? -99,
    },
    {
      key: 'freq',
      header: 'Dias umidos',
      align: 'num',
      cell: (a) => a.freq_dias_umidos.toFixed(3),
      sortValue: (a) => a.freq_dias_umidos,
    },
    {
      key: 'p95',
      header: 'p95 (mm)',
      align: 'num',
      cell: (a) => a.p95_mm.toFixed(2),
      sortValue: (a) => a.p95_mm,
    },
    {
      key: 'total',
      header: 'Total (mm)',
      align: 'num',
      cell: (a) => a.total_mm.toFixed(0),
      sortValue: (a) => a.total_mm,
    },
    {
      key: 'n',
      header: 'Estacoes',
      align: 'num',
      cell: (a) => a.n_estacoes,
      sortValue: (a) => a.n_estacoes,
    },
  ];

  return (
    <View
      title="Historico"
      intro="Meio seculo de primaveras medidas no RS: com que frequencia choveu, com que intensidade, e quanto disso o El Nino explica."
    >
      <QueryState isLoading={isLoading} isError={isError}>
        {data && !data.disponivel && (
          <Empty>{data.motivo ?? 'Camada historica nao calculada.'}</Empty>
        )}

        {data?.disponivel && data.meta && (
          <>
            {/* O aviso de contato com o alvo vem ANTES de qualquer numero:
                e a consequencia mais duradoura desta tela para o projeto. */}
            <p className="aviso-escopo t-note">
              <strong>Contato com o alvo (ADR-004).</strong> Estes numeros olham a variavel que a
              engine tenta prever. A partir daqui, mudar <code>feature_blocks.yaml</code> invalida o
              experimento. Nada aqui e modelo: e contagem e intervalo por reamostragem — nenhum
              preditor foi selecionado, nenhum parametro foi ajustado.
            </p>

            <Section
              title="A base"
              note={`Fonte: ${data.meta.fonte}. Estacao-alvo ${data.meta.estacao_alvo}, dia umido >= ${data.meta.limiar_dia_umido_mm} mm, minimo de ${data.meta.cobertura_minima_dias} dias por temporada.`}
            >
              <Grid min={200}>
                <Metrica n={data.meta.n_estacoes} label="estacoes dentro do poligono do RS" />
                <Metrica n={data.meta.n_temporadas_estacao} label="temporadas-estacao com cobertura" />
                <Metrica
                  n={`${data.meta.periodo[0]}–${data.meta.periodo[1]}`}
                  label="periodo coberto"
                />
                <Metrica
                  n={
                    data.meta.periodo_com_oni
                      ? `${data.meta.periodo_com_oni[0]}–${data.meta.periodo_com_oni[1]}`
                      : '—'
                  }
                  label="interseccao com o ONI"
                />
              </Grid>
            </Section>

            {data.composto?.deslocamento_elnino_vs_neutro && (
              <Section
                title="El Nino molha o RS?"
                note="Deslocamento El Nino menos Neutro, com IC 90% por bootstrap (2000 reamostras, semente fixa). O criterio de leitura e o mesmo espirito da ADR-007: so conta o que nao cruza zero."
              >
                <Grid min={260}>
                  {METRICAS.map((m) => {
                    const d = data.composto!.deslocamento_elnino_vs_neutro![m.id];
                    if (!d) return null;
                    return (
                      <Panel key={m.id} tone={d.separa_de_zero ? undefined : 'verdict'}>
                        <p className="t-section">{m.label}</p>
                        <Row>
                          <span className="t-hero" data-sep={d.separa_de_zero ? 'sim' : undefined}>
                            {d.delta > 0 ? '+' : ''}
                            {d.delta.toFixed(m.casas)}
                          </span>
                          <span className="t-note">{m.unidade}</span>
                        </Row>
                        <p className="t-data ic">
                          IC90 [{d.ic90[0].toFixed(m.casas)}, {d.ic90[1].toFixed(m.casas)}]
                        </p>
                        <p className={`t-small veredito${d.separa_de_zero ? '' : ' veredito--cruza'}`}>
                          {d.separa_de_zero
                            ? 'separa de zero — o deslocamento se sustenta'
                            : 'cruza zero — nao se sustenta neste n'}
                        </p>
                      </Panel>
                    );
                  })}
                </Grid>
              </Section>
            )}

            {data.composto?.fases && (
              <Section title="Por fase ENSO" note="Media entre estacoes, IC 90% por bootstrap.">
                <Grid min={260}>
                  {Object.entries(data.composto.fases).map(([fase, d]) => (
                    <Panel
                      key={fase}
                      title={`${fase} — ${d.n_anos} anos`}
                      actions={<ProvenanceBadge basis="measured" />}
                    >
                      <ul className="lista-marcas">
                        {METRICAS.map((m) => {
                          const v = d[m.id];
                          if (!v) return null;
                          return (
                            <li key={m.id}>
                              {m.label}: <strong>{v.media.toFixed(m.casas)}</strong>{' '}
                              <span className="t-note">
                                [{v.ic90[0].toFixed(m.casas)}, {v.ic90[1].toFixed(m.casas)}]
                              </span>
                            </li>
                          );
                        })}
                      </ul>
                    </Panel>
                  ))}
                </Grid>
              </Section>
            )}

            <Section title="Cada primavera, do mais seco ao mais umido">
              <Panel pad="tight">
                <SerieAnos anos={anos} />
              </Panel>
            </Section>

            <Section title="Tabela completa">
              <DataTable
                columns={colunas}
                rows={anos}
                rowKey={(a) => a.ano}
                defaultSort={{ key: 'ano', dir: 'asc' }}
              />
            </Section>

            <Section title="Limites">
              <Panel tone="verdict">
                <ul className="lista-marcas" data-tom="alerta">
                  {data.meta.limites.map((l) => (
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

function Metrica({ n, label }: { n: number | string; label: string }) {
  return (
    <Panel>
      <p className="t-hero">{typeof n === 'number' ? n.toLocaleString('pt-BR') : n}</p>
      <p className="t-small">{label}</p>
    </Panel>
  );
}

/**
 * Barras por ano, coloridas pelo ONI da propria temporada.
 *
 * SVG a mao em vez de biblioteca: sao ~50 barras e um eixo. A cor sai da
 * escala divergente do dado (FRIO/QUENTE), que aqui e legitima — o valor
 * colorido E uma anomalia de ENSO, nao cromo de interface.
 */
function SerieAnos({ anos }: { anos: { ano: number; total_mm: number; oni_ond: number | null }[] }) {
  if (anos.length === 0) return <Empty>Sem temporadas com cobertura suficiente.</Empty>;
  const W = 960;
  const H = 260;
  const PAD = { l: 46, r: 12, t: 12, b: 28 };
  const max = Math.max(...anos.map((a) => a.total_mm));
  const larg = (W - PAD.l - PAD.r) / anos.length;

  return (
    <svg className="serie" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Total de chuva OND por ano">
      {[0, 0.25, 0.5, 0.75, 1].map((f) => {
        const y = PAD.t + (1 - f) * (H - PAD.t - PAD.b);
        return (
          <g key={f}>
            <line x1={PAD.l} y1={y} x2={W - PAD.r} y2={y} stroke={GRID} strokeWidth="1" />
            <text x={PAD.l - 6} y={y + 4} className="serie__tick" textAnchor="end">
              {Math.round(f * max)}
            </text>
          </g>
        );
      })}
      {anos.map((a, i) => {
        const h = (a.total_mm / max) * (H - PAD.t - PAD.b);
        const cor = a.oni_ond === null ? GRID : divergingValue(a.oni_ond, 2.5);
        return (
          <rect
            key={a.ano}
            x={PAD.l + i * larg + 0.5}
            y={H - PAD.b - h}
            width={Math.max(larg - 1.5, 1)}
            height={h}
            fill={alpha(cor, 0.9)}
          >
            <title>
              {a.ano}: {a.total_mm.toFixed(0)} mm
              {a.oni_ond !== null ? ` · ONI ${a.oni_ond.toFixed(2)}` : ''}
            </title>
          </rect>
        );
      })}
      {anos
        .filter((_, i) => i % 5 === 0)
        .map((a) => {
          const i = anos.indexOf(a);
          return (
            <text
              key={a.ano}
              x={PAD.l + i * larg + larg / 2}
              y={H - 8}
              className="serie__tick"
              textAnchor="middle"
            >
              {a.ano}
            </text>
          );
        })}
    </svg>
  );
}
