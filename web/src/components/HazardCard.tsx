import type { CSSProperties } from 'react';
import type { Hazard } from '../api/types';
import { ProvenanceBadge } from './ProvenanceBadge';
import { NIVEL, NIVEL_FRACAO } from '../theme/palette';
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
 * Nivel de perigo usa a escala ordinal NIVEL de theme/palette (dado, nao
 * cromo de UI) com a codificacao PRIMARIA no COMPRIMENTO da barra: a cor e
 * reforco. Continua valendo que o texto nao veste a cor — o rotulo fica em
 * giz e a cor mora na barra ao lado.
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
          {hazard.level && hazard.level in NIVEL && (
            <div
              className="hazard-card__gauge"
              style={
                {
                  '--nivel-cor': NIVEL[hazard.level as keyof typeof NIVEL],
                  '--nivel-fracao': `${NIVEL_FRACAO[hazard.level as keyof typeof NIVEL] * 100}%`,
                } as CSSProperties
              }
              role="presentation"
            />
          )}
          {hazard.drivers.length > 0 && (
            <p className="muted">motores: {hazard.drivers.join(', ')}</p>
          )}
          <p className="muted hazard-card__limits">{hazard.limits}</p>
        </>
      )}
    </article>
  );
}
