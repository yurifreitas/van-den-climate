import type { Basis } from '../api/types';
import './ProvenanceBadge.css';

/**
 * Selo de proveniencia (§0 do contrato, regra transversal do brief):
 * todo painel com numero derivado precisa exibir isto — numero sem selo e
 * bug de interface, nao escolha de design.
 *
 * Usa SOMENTE giz/bruma. A distincao measured/modeled/synthetic e feita por
 * ESTILO DE BORDA (solida = medido, tracejada = sintetico/modelado), nunca
 * por cor — cor e reservada a anomalia (FRIO/QUENTE), nem aqui.
 */
const LABEL: Record<Basis, string> = {
  measured: 'medido',
  modeled: 'modelado',
  synthetic: 'sintetico',
};

export function ProvenanceBadge({ basis }: { basis: Basis | null }) {
  if (basis === null) {
    return (
      <span className="provenance-badge provenance-badge--absent" title="Fonte ausente — sem proveniencia">
        sem fonte
      </span>
    );
  }
  const variant = basis === 'measured' ? 'solid' : 'dashed';
  return (
    <span className={`provenance-badge provenance-badge--${variant}`} title={`Base epistemica: ${LABEL[basis]}`}>
      {LABEL[basis]}
    </span>
  );
}
