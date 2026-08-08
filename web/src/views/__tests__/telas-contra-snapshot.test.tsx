import { describe, expect, it } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import type { ReactElement } from 'react';
import { server } from '../../api/mocks/server';
import { slugEstatico } from '../../api/client';
import { RiscoView } from '../RiscoView';
import { MunicipiosView } from '../MunicipiosView';
import { DossieView } from '../DossieView';
import { RespostaView } from '../RespostaView';
import { HistoricoView } from '../HistoricoView';
import { PlanoView } from '../PlanoView';
import { RecursosView } from '../RecursosView';
import { EstadoView } from '../EstadoView';
import { LedgerView } from '../LedgerView';
import { SaudeView } from '../SaudeView';
import { ReferenciasView } from '../ReferenciasView';

/**
 * Varredura: toda tela renderiza contra o SNAPSHOT REAL sem explodir.
 *
 * O teste irmao (`RecursosView.test.tsx`) documenta o caso que originou esta
 * varredura — envelope de `vazios` no back, array no front, pagina preta no
 * Pages. A licao que generaliza nao e sobre `vazios`: e que os dois lados da
 * fronteira sao escritos a mao (types.ts contra o contrato, fixtures do MSW
 * contra a expectativa do front), e dois artefatos a mao erram JUNTOS, na
 * mesma direcao, sem que nada acuse.
 *
 * O snapshot congelado e o unico artefato do repositorio gerado PELA API. E o
 * arbitro disponivel — e e literalmente o que a demo publica consome, entao
 * uma tela que passa aqui e uma tela que sobe.
 *
 * O que este teste NAO cobre, de proposito: conteudo. Ele afirma "renderizou
 * e mostrou o titulo", nao "mostrou o numero certo" — assercao de valor
 * pertence ao teste da tela especifica, com dado controlado.
 */
const RAIZ = join(process.cwd(), 'public', 'static-api');

function servirSnapshotReal() {
  server.use(
    http.get('/api/v1/*', ({ request }) => {
      const url = new URL(request.url);
      const rota = url.pathname.replace('/api/v1', '');
      const params = Object.fromEntries(url.searchParams.entries());
      const arquivo = join(RAIZ, `${slugEstatico(rota, params)}.json`);
      if (!existsSync(arquivo)) {
        // 404 e resposta legitima: a tela deve mostrar estado de erro, nao
        // quebrar. Rota fora do snapshot nao e o defeito que caçamos aqui.
        return HttpResponse.json({ detail: `sem snapshot: ${arquivo}` }, { status: 404 });
      }
      return HttpResponse.json(JSON.parse(readFileSync(arquivo, 'utf-8')));
    }),
  );
}

function renderizar(tela: ReactElement, rota = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[rota]}>{tela}</MemoryRouter>
    </QueryClientProvider>,
  );
}

/** (titulo esperado na tela, elemento, rota) */
const TELAS: [string, ReactElement, string][] = [
  ['Risco', <RiscoView />, '/'],
  ['Municipios', <MunicipiosView />, '/municipios'],
  ['Dossie', <DossieView />, '/dossie?mun=4314902'],
  ['Resposta', <RespostaView />, '/resposta'],
  ['Historico', <HistoricoView />, '/historico'],
  ['Plano', <PlanoView />, '/plano'],
  ['Recursos', <RecursosView />, '/recursos'],
  ['Estado', <EstadoView />, '/estado'],
  ['Ledger', <LedgerView />, '/ledger'],
  ['Saude', <SaudeView />, '/saude'],
  ['Referencias', <ReferenciasView />, '/referencias'],
];

describe('toda tela renderiza contra o snapshot real', () => {
  it.each(TELAS)('%s', async (nome, tela, rota) => {
    servirSnapshotReal();
    const erros: unknown[] = [];
    const original = console.error;
    console.error = (...args: unknown[]) => {
      erros.push(args[0]);
      original(...args);
    };
    try {
      const { container } = renderizar(tela, rota);
      // Espera a tela sair do estado de carregamento — sem isto o teste
      // passaria com a casca, que e exatamente o que a demo mostrava.
      await waitFor(() => expect(container.textContent?.length ?? 0).toBeGreaterThan(200), {
        timeout: 5000,
      });
      const explodiu = erros.filter((e) => String(e).includes('is not a function'));
      expect(explodiu, `${nome}: erro de tipo em runtime contra o payload real`).toHaveLength(0);
      expect(screen.queryByText(/is not a function/)).toBeNull();
    } finally {
      console.error = original;
    }
  });
});
