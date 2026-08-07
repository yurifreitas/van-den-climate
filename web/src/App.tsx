import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/Layout';
import { RiscoView } from './views/RiscoView';
import { MunicipiosView } from './views/MunicipiosView';
import { EstadoView } from './views/EstadoView';
import { PrevisaoView } from './views/PrevisaoView';
import { EvidenciaView } from './views/EvidenciaView';
import { LedgerView } from './views/LedgerView';
import { SaudeView } from './views/SaudeView';
import { ReferenciasView } from './views/ReferenciasView';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      {/* `basename` e obrigatorio quando o site nao mora na raiz do dominio.
          No GitHub Pages a URL e /van-den-climate/, e sem isto NENHUMA rota
          casa: a pagina carrega, nao da erro no console, e renderiza vazio —
          o modo de falha mais dificil de diagnosticar que existe. */}
      <BrowserRouter basename={import.meta.env.BASE_URL}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<RiscoView />} />
            <Route path="/municipios" element={<MunicipiosView />} />
            <Route path="/estado" element={<EstadoView />} />
            <Route path="/previsao" element={<PrevisaoView />} />
            <Route path="/evidencia" element={<EvidenciaView />} />
            <Route path="/ledger" element={<LedgerView />} />
            <Route path="/saude" element={<SaudeView />} />
            <Route path="/referencias" element={<ReferenciasView />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
