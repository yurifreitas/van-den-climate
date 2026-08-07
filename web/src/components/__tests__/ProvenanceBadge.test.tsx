import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ProvenanceBadge } from '../ProvenanceBadge';

describe('ProvenanceBadge', () => {
  it('measured renderiza borda solida', () => {
    render(<ProvenanceBadge basis="measured" />);
    const el = screen.getByText('medido');
    expect(el.className).toContain('provenance-badge--solid');
  });

  it('synthetic renderiza borda tracejada', () => {
    render(<ProvenanceBadge basis="synthetic" />);
    const el = screen.getByText('sintetico');
    expect(el.className).toContain('provenance-badge--dashed');
  });

  it('basis null (fonte ausente) nao quebra e avisa', () => {
    render(<ProvenanceBadge basis={null} />);
    expect(screen.getByText('sem fonte')).toBeInTheDocument();
  });
});
