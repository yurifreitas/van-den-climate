import { useState } from 'react';
import { useForecastAnalogs, useForecastAttribution } from '../api/hooks';
import { QueryState } from '../components/QueryState';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { AttributionChart } from '../components/AttributionChart';
import { View, Panel, Field, DataTable } from '../components/ui';
import type { Column } from '../components/ui';
import './views.css';

const SEASONS = ['OND2026', 'JFM2027'];

const TERCIL = ['Abaixo', 'Perto', 'Acima'];

type Analog = { year: number; similarity: number; observed_tercile: number };

const ANALOG_COLUMNS: Column<Analog>[] = [
  { key: 'year', header: 'ano', align: 'num', cell: (a) => a.year, sortValue: (a) => a.year },
  {
    key: 'similarity',
    header: 'similaridade',
    align: 'num',
    cell: (a) => a.similarity.toFixed(2),
    sortValue: (a) => a.similarity,
  },
  {
    key: 'tercile',
    header: 'tercil observado',
    align: 'num',
    cell: (a) => TERCIL[a.observed_tercile] ?? '—',
  },
];

/**
 * Rota `/evidencia` — pergunta: "o que sustenta esta previsao? Quanto
 * some se removermos ENSO, e quais anos historicos mais se parecem com
 * agora?"
 */
export function EvidenciaView() {
  const [season, setSeason] = useState(SEASONS[0]);
  const attribution = useForecastAttribution(season);
  const analogs = useForecastAnalogs(season);

  return (
    <View
      title="Evidencia"
      intro="O que sustenta esta previsao: quanto some sem ENSO, e quais anos historicos mais se parecem com agora."
      actions={
        <Field label="temporada:">
          <select value={season} onChange={(e) => setSeason(e.target.value)}>
            {SEASONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </Field>
      }
    >
      <Panel
        title="Atribuicao por bloco"
        actions={
          attribution.data && <ProvenanceBadge basis={attribution.data.provenance.basis} />
        }
      >
        <QueryState isLoading={attribution.isLoading} isError={attribution.isError}>
          {attribution.data && <AttributionChart blocks={attribution.data.shares} />}
        </QueryState>
      </Panel>

      <Panel
        title="Anos analogos"
        actions={analogs.data && <ProvenanceBadge basis={analogs.data.provenance.basis} />}
      >
        <QueryState isLoading={analogs.isLoading} isError={analogs.isError}>
          <DataTable
            columns={ANALOG_COLUMNS}
            rows={analogs.data?.analogs ?? []}
            rowKey={(a) => a.year}
            defaultSort={{ key: 'similarity', dir: 'desc' }}
            empty="Nenhum ano analogo para esta temporada."
          />
        </QueryState>
      </Panel>
    </View>
  );
}
