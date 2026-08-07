import { useHealthBreaks, useHealthCoverage, useHealthSources } from '../api/hooks';
import { QueryState } from '../components/QueryState';
import { CoverageMatrix } from '../components/CoverageMatrix';
import { View, Panel, DataTable } from '../components/ui';
import type { Column } from '../components/ui';
import './views.css';

const STATUS_LABEL: Record<string, string> = { ok: 'ok', stale: 'desatualizado', failed: 'falhou' };

type Source = {
  source_id: string;
  last_ingested_at: string | null;
  rows: number | null;
  sha256: string | null;
  status: string;
};
type Break = { label: string; detected_at: string; description: string };

const SOURCE_COLUMNS: Column<Source>[] = [
  { key: 'id', header: 'fonte', align: 'num', cell: (s) => s.source_id, sortValue: (s) => s.source_id },
  {
    key: 'ingested',
    header: 'ultima ingestao',
    align: 'num',
    cell: (s) => s.last_ingested_at ?? '— (lacuna declarada)',
    sortValue: (s) => s.last_ingested_at ?? '',
  },
  { key: 'rows', header: 'linhas', align: 'num', cell: (s) => s.rows ?? '—' },
  {
    key: 'hash',
    header: 'hash',
    align: 'num',
    // hash completo e ilegivel na tabela; os 12 primeiros caracteres ja
    // identificam o download de forma unica — o resto vai no title.
    cell: (s) => s.sha256?.slice(0, 12) ?? '—',
    title: (s) => s.sha256 ?? undefined,
  },
  { key: 'status', header: 'status', align: 'num', cell: (s) => STATUS_LABEL[s.status] ?? s.status },
];

const BREAK_COLUMNS: Column<Break>[] = [
  { key: 'label', header: 'estacao', cell: (b) => b.label },
  {
    key: 'detected',
    header: 'detectada em',
    align: 'num',
    cell: (b) => b.detected_at,
    sortValue: (b) => b.detected_at,
  },
  { key: 'desc', header: 'descricao', cell: (b) => b.description },
];

/**
 * Rota `/saude` — pergunta: "a rede de estacoes tem cobertura suficiente,
 * onde ha quebras de homogeneidade, e as fontes de ingestao estao vivas?"
 *
 * Fonte que falhou vira LACUNA DECLARADA na tabela (status "falhou"), nunca
 * uma excecao silenciosa que derruba a tela (regra 3 do contrato).
 */
export function SaudeView() {
  const coverage = useHealthCoverage();
  const breaks = useHealthBreaks();
  const sources = useHealthSources();

  return (
    <View
      title="Saude dos dados"
      intro="Se a rede de estacoes tem cobertura suficiente, onde ha quebras de homogeneidade, e se as fontes de ingestao estao vivas."
    >
      <Panel title="Status das fontes">
        <QueryState isLoading={sources.isLoading} isError={sources.isError}>
          <DataTable
            columns={SOURCE_COLUMNS}
            rows={sources.data?.sources ?? []}
            rowKey={(s) => s.source_id}
            empty="Nenhuma fonte registrada."
          />
        </QueryState>
      </Panel>

      <Panel title="Cobertura — sinal x ano">
        <QueryState isLoading={coverage.isLoading} isError={coverage.isError}>
          <CoverageMatrix cells={coverage.data?.cells ?? []} />
        </QueryState>
      </Panel>

      <Panel title="Quebras de homogeneidade">
        <QueryState isLoading={breaks.isLoading} isError={breaks.isError}>
          <DataTable
            columns={BREAK_COLUMNS}
            rows={breaks.data?.breaks ?? []}
            rowKey={(_, i) => i}
            defaultSort={{ key: 'detected', dir: 'desc' }}
            empty="Nenhuma quebra de homogeneidade detectada."
          />
        </QueryState>
      </Panel>
    </View>
  );
}
