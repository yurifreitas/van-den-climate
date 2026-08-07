import { describe, expect, it } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { RiscoView } from '../RiscoView';

function renderWithProviders() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <RiscoView />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('RiscoView (dados mockados via MSW)', () => {
  it('renderiza o card de flash_flood fora de escopo mesmo entre perigos com nivel', async () => {
    renderWithProviders();
    await waitFor(() => expect(screen.getByText('Cheia rapida')).toBeInTheDocument());
    expect(screen.getByText('FORA DE ESCOPO DESTA ENGINE')).toBeInTheDocument();
    expect(screen.getByText('Excesso de chuva sazonal OND')).toBeInTheDocument();
  });
});
