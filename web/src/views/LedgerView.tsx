import { useLedger, useLedgerSkill } from '../api/hooks';
import { QueryState } from '../components/QueryState';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { View, Panel, DataTable } from '../components/ui';
import type { Column } from '../components/ui';
import './views.css';

/** Metrica ausente e "—", nunca 0 nem tela quebrada. */
const num = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : v.toFixed(3);

const TERCIL = ['Abaixo', 'Perto', 'Acima'];

type Metric = {
  metric: string;
  point: number | null;
  lo: number | null;
  hi: number | null;
  permutation_null: number | null;
};
type Entry = {
  target_id: string;
  issued_at: string;
  predicted_tercile: number;
  observed_tercile: number | null;
};

/*
 * `num(...)` em vez de `.toFixed()` direto: com nenhum modelo aceito sob a
 * ADR-007, a API devolve `null` — que e o RESULTADO correto, nao ausencia de
 * dado. Chamar .toFixed() em null derrubava a tela justamente no estado que o
 * projeto considera certo.
 */
const SKILL_COLUMNS: Column<Metric>[] = [
  { key: 'metric', header: 'metrica', cell: (m) => m.metric },
  { key: 'point', header: 'ponto', align: 'num', cell: (m) => num(m.point) },
  { key: 'ci', header: 'IC90', align: 'num', cell: (m) => `[${num(m.lo)}, ${num(m.hi)}]` },
  {
    key: 'null',
    header: 'nulo de permutacao',
    align: 'num',
    cell: (m) => num(m.permutation_null),
  },
];

const ENTRY_COLUMNS: Column<Entry>[] = [
  { key: 'target_id', header: 'alvo', cell: (e) => e.target_id, sortValue: (e) => e.target_id },
  {
    key: 'issued_at',
    header: 'emitido em',
    align: 'num',
    cell: (e) => e.issued_at,
    sortValue: (e) => e.issued_at,
  },
  { key: 'predicted', header: 'previsto', align: 'num', cell: (e) => TERCIL[e.predicted_tercile] },
  {
    key: 'observed',
    header: 'observado',
    align: 'num',
    cell: (e) => (e.observed_tercile === null ? '—' : TERCIL[e.observed_tercile]),
  },
];

/**
 * Rota `/ledger` — pergunta: "o que foi previsto de fato, o que foi
 * observado, e qual o skill medido com incerteza (nao um numero solto)?"
 * Ledger e imutavel (append-only, contrato §4) — por isso e tabela, nao
 * grafico editavel.
 */
export function LedgerView() {
  const ledger = useLedger();
  const skill = useLedgerSkill();

  return (
    <View
      title="Ledger"
      intro="O que foi previsto de fato, o que foi observado, e o skill medido com incerteza. Registro imutavel, append-only."
    >
      <Panel
        title="Skill (RPSS/BSS)"
        actions={skill.data && <ProvenanceBadge basis={skill.data.provenance.basis} />}
      >
        <QueryState isLoading={skill.isLoading} isError={skill.isError}>
          <DataTable
            columns={SKILL_COLUMNS}
            rows={skill.data?.metrics ?? []}
            rowKey={(m) => m.metric}
            empty="Nenhuma metrica de skill calculada."
          />
        </QueryState>
      </Panel>

      <Panel title="Previsoes emitidas (append-only)">
        <QueryState isLoading={ledger.isLoading} isError={ledger.isError}>
          <DataTable
            columns={ENTRY_COLUMNS}
            rows={ledger.data?.entries ?? []}
            rowKey={(_, i) => i}
            defaultSort={{ key: 'issued_at', dir: 'desc' }}
            empty="Nenhuma previsao emitida ainda."
          />
        </QueryState>
      </Panel>
    </View>
  );
}
