import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.tsx';

/**
 * MSW so entra em dev/preview quando `VITE_USE_MSW=true` (ou por padrao em
 * dev) — a API pode nao estar pronta (ver briefing), entao o mock preenche
 * a lacuna sem exigir `api/` rodando. Em producao, o fetch real via
 * vite.config.ts (dev) ou reverse proxy (build) assume.
 */
async function prepare() {
  // Padrao DESLIGADO. Mock so entra com VITE_USE_MSW=true explicito.
  // O default anterior (ligado em dev, salvo opt-out) fazia a tela mostrar
  // numero inventado com selo "MEDIDO" enquanto a API real servia outro
  // valor — numa central de risco esse e o pior default possivel.
  if (import.meta.env.DEV && import.meta.env.VITE_USE_MSW === 'true') {
    const { worker } = await import('./api/mocks/browser');
    await worker.start({ onUnhandledRequest: 'bypass' });
  }
}

prepare().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
});
