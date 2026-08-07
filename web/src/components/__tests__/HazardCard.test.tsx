import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { HazardCard } from '../HazardCard';
import { riskFixture } from '../../api/mocks/fixtures';

describe('HazardCard — regra critica do flash_flood', () => {
  it('renderiza o aviso de fora-de-escopo quando level=null, sem omitir o card', () => {
    const flash = riskFixture.hazards.find((h) => h.id === 'flash_flood')!;
    render(<HazardCard hazard={flash} />);
    expect(screen.getByText('FORA DE ESCOPO DESTA ENGINE')).toBeInTheDocument();
    expect(screen.getByText(/Defesa Civil/)).toBeInTheDocument();
  });

  it('perigo com level definido renderiza o nivel normalmente', () => {
    const wet = riskFixture.hazards.find((h) => h.id === 'seasonal_wet_anomaly')!;
    render(<HazardCard hazard={wet} />);
    expect(screen.getByText('elevado')).toBeInTheDocument();
  });
});
