import { useHazardsCatalog } from '../api/hooks';
import { HazardCard } from '../components/HazardCard';
import { QueryState } from '../components/QueryState';

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
    <section>
      <h2>Risco — carta de perigos ativos</h2>
      <p className="muted">
        Cada perigo e mostrado no horizonte que a engine sustenta. Um horizonte sem
        camada construida aparece declarado, nao omitido.
      </p>
      <QueryState isLoading={isLoading} isError={isError}>
        {['seasonal', 'subseasonal', 'synoptic'].map((horizon) => (
          <div key={horizon} className="risco-group">
            <h3 className="risco-group__title">{HORIZON_LABEL[horizon]}</h3>
            <div className="risco-group__grid">
              {(grouped[horizon] ?? []).length === 0 ? (
                <p className="muted">Nenhum perigo catalogado neste horizonte.</p>
              ) : (
                grouped[horizon]!.map((h) => <HazardCard key={h.id} hazard={h} />)
              )}
            </div>
          </div>
        ))}
      </QueryState>
    </section>
  );
}
