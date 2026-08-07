import { Link } from 'react-router-dom';
import { useHazardsCatalog } from '../api/hooks';
import { HazardCard } from '../components/HazardCard';
import { MapaTeleconexao } from '../components/MapaTeleconexao';
import { QueryState } from '../components/QueryState';
import { View, Section, Grid, Empty, Panel } from '../components/ui';

/**
 * Rota `/` — pergunta que responde: "quais perigos climaticos estao ativos
 * agora no RS, e em qual horizonte a engine pode falar sobre eles?"
 *
 * Agrupa por horizonte (sazonal / sub-sazonal / sinotico) porque essa e a
 * separacao que o pivo para central de risco introduziu (ADR-013, §pivô de
 * front). O card sinotico (`flash_flood`, level:null) SEMPRE aparece —
 * nunca filtrado, mesmo que a lista de horizontes sinoticos fique vazia
 * sem ele.
 */
const HORIZON_LABEL: Record<string, string> = {
  seasonal: 'Sazonal (OND) — desloca probabilidade de fundo',
  subseasonal: 'Sub-sazonal (2-6 semanas) — janelas via MJO/regime',
  synoptic: 'Sinotico (1-7 dias) — fora de escopo desta engine',
};

export function RiscoView() {
  const { data, isLoading, isError } = useHazardsCatalog();

  const grouped = data
    ? data.hazards.reduce<Record<string, typeof data.hazards>>((acc, h) => {
        (acc[h.horizon] ??= []).push(h);
        return acc;
      }, {})
    : {};

  return (
    <View
      title="Risco"
      intro="Quais perigos climaticos estao ativos agora no RS, e em qual horizonte a engine pode falar sobre eles."
    >
      {/* Onde o sinal nasce e onde ele chega. Fica ACIMA dos cards: a
          pergunta geografica ("isto e sobre onde?") se responde antes da
          lista de perigos, nao depois. */}
      <Section
        title="Geografia do sinal — Pacifico equatorial → RS"
        note={
          <>
            Este mapa para no contorno do estado: o sinal sazonal e estadual e nao tem resolucao
            municipal. Para descer ao municipio — impacto observado em 2024, deficit de prevencao
            declarado e prioridade preventiva — veja <Link to="/municipios">Municipios</Link>.
          </>
        }
      >
        <Panel pad="tight">
          <MapaTeleconexao />
        </Panel>
      </Section>

      <QueryState isLoading={isLoading} isError={isError}>
        {['seasonal', 'subseasonal', 'synoptic'].map((horizon) => (
          <Section key={horizon} title={HORIZON_LABEL[horizon]}>
            <Grid min={220}>
              {(grouped[horizon] ?? []).length === 0 ? (
                <Empty>Nenhum perigo catalogado neste horizonte.</Empty>
              ) : (
                grouped[horizon]!.map((h) => <HazardCard key={h.id} hazard={h} />)
              )}
            </Grid>
          </Section>
        ))}
      </QueryState>
    </View>
  );
}
