import { describe, expect, it } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { server } from '../../api/mocks/server';
import { slugEstatico } from '../../api/client';
import { RecursosView } from '../RecursosView';

/**
 * Regressao da demo em branco de 2026-08-08.
 *
 * A API passou a envelopar `vazios` num objeto com selo e nota proprios — o
 * cadastro de recursos e medido, a ORDEM da lista nao e, e as duas coisas nao
 * podem dividir o mesmo selo. O front continuou tratando `vazios` como array.
 *
 * Nada pegou: `types.ts` e escrito a mao contra o contrato, entao o TypeScript
 * concordou com a declaracao errada; os fixtures do MSW sao escritos a mao
 * tambem, e foram atualizados junto com o front que ja estava errado. Os dois
 * lados mentiam a mesma mentira. A tela so morreu no GitHub Pages, com
 * `TypeError: s.map is not a function` e uma pagina preta.
 *
 * Por isso este teste NAO usa fixture: ele responde com o snapshot real, o
 * mesmo arquivo que a demo publica consome. Fixture a mao verifica que o
 * front concorda consigo mesmo; snapshot real verifica que ele concorda com
 * a API.
 */
const RAIZ = join(process.cwd(), 'public', 'static-api');

/** Serve qualquer rota /api/v1 a partir do snapshot congelado, se houver arquivo. */
function servirSnapshotReal() {
  server.use(
    http.get('/api/v1/*', ({ request }) => {
      const url = new URL(request.url);
      const rota = url.pathname.replace('/api/v1', '');
      const params = Object.fromEntries(url.searchParams.entries());
      const arquivo = join(RAIZ, `${slugEstatico(rota, params)}.json`);
      if (!existsSync(arquivo)) {
        return HttpResponse.json({ detail: `sem snapshot: ${arquivo}` }, { status: 404 });
      }
      return HttpResponse.json(JSON.parse(readFileSync(arquivo, 'utf-8')));
    }),
  );
}

function renderizar() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <RecursosView />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('RecursosView contra o snapshot real', () => {
  it('renderiza a tabela de vazios a partir do envelope com selo proprio', async () => {
    servirSnapshotReal();
    renderizar();

    await waitFor(() => expect(screen.getByText('Onde realocar primeiro')).toBeInTheDocument());

    // O selo do envelope: a ordem da lista e composta, nunca medida.
    await waitFor(() => expect(screen.getAllByText('modelado').length).toBeGreaterThan(0));

    // E a lista de fato saiu do envelope — se `vazios` voltar a ser lido como
    // array, nao ha linha nenhuma aqui (ou o render explode, como explodiu).
    const dados = JSON.parse(readFileSync(join(RAIZ, 'recursos.json'), 'utf-8'));
    const primeiro = dados.vazios.itens[0];
    expect(primeiro, 'snapshot sem vazios — o teste perdeu o objeto').toBeTruthy();
    await waitFor(() =>
      expect(screen.getAllByText(primeiro.municipio).length).toBeGreaterThan(0),
    );
  });
});
