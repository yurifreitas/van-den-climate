/**
 * Verifica que os fixtures (exemplos fieis ao contrato) satisfazem os
 * tipos TS gerados a mao a partir de docs/API_CONTRACT.md. Se o contrato
 * mudar e alguem esquecer de atualizar types.ts, este arquivo nao compila
 * — falha em tempo de tipo, nao so em runtime.
 */
import { describe, expect, it } from 'vitest';
import type {
  ForecastResponse,
  RiskResponse,
  StateResponse,
} from '../types';
import {
  forecastNotAcceptedFixture,
  riskFixture,
  stateFixture,
} from '../mocks/fixtures';

describe('fixtures batem com os tipos do contrato', () => {
  it('StateResponse', () => {
    const s: StateResponse = stateFixture;
    expect(s.blocks.length).toBeGreaterThan(0);
    expect(s.blocks[0].provenance.basis).toBe('measured');
  });

  it('ForecastResponse — not_accepted e um resultado valido, nao erro', () => {
    const f: ForecastResponse = forecastNotAcceptedFixture;
    expect(f.status).toBe('not_accepted');
    expect(f.acceptance.rpss.point).toBeNull();
    expect(f.targets).toHaveLength(3);
  });

  it('RiskResponse — flash_flood tem level null e basis null', () => {
    const r: RiskResponse = riskFixture;
    const flash = r.hazards.find((h) => h.id === 'flash_flood');
    expect(flash).toBeDefined();
    expect(flash!.level).toBeNull();
    expect(flash!.basis).toBeNull();
    expect(flash!.horizon).toBe('synoptic');
  });
});
