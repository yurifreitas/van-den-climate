import type { Hazard } from '../api/types';
import { ProvenanceBadge } from './ProvenanceBadge';
import './HazardCard.css';

const LEVEL_LABEL: Record<string, string> = {
  low: 'baixo',
  moderate: 'moderado',
  elevated: 'elevado',
  high: 'alto',
};

/**
 * Card de perigo por horizonte. REGRA MAIS IMPORTANTE do brief: quando
 * `level === null` (caso de `flash_flood`), o card renderiza EXPLICITAMENTE
 * como fora de escopo, com encaminhamento a Defesa Civil/SEMA-RS — nunca
 * omitido, nunca escondido atras de um estado vazio generico.
 *
 * Nivel de perigo NAO usa FRIO/QUENTE (essas cores sao so para anomalia de
 * dado nos graficos) — usa intensidade de giz/bruma e um marcador textual,
 * preservando a regra de isolamento de paleta.
 */
export function HazardCard({ hazard }: { hazard: Hazard }) {
  const outOfScope = hazard.level === null;
  return (
    <article className={`hazard-card${outOfScope ? ' hazard-card--out-of-scope' : ''}`}>
      <header className="hazard-card__header">
        <h3>{hazard.label}</h3>
        <ProvenanceBadge basis={hazard.basis} />
      </header>
      <p className="muted hazard-card__horizon">horizonte: {hazard.horizon}</p>

      {outOfScope ? (
        <div className="hazard-card__scope-warning" role="note">
          <p className="hazard-card__scope-title">FORA DE ESCOPO DESTA ENGINE</p>
          <p>{hazard.limits}</p>
        </div>
      ) : (
        <>
          <p className="hazard-card__level">
            nivel: <strong>{LEVEL_LABEL[hazard.level ?? ''] ?? hazard.level}</strong>
          </p>
          {hazard.drivers.length > 0 && (
            <p className="muted">motores: {hazard.drivers.join(', ')}</p>
          )}
          <p className="muted hazard-card__limits">{hazard.limits}</p>
        </>
      )}
    </article>
  );
}
