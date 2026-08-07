import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/Layout';
import { RiscoView } from './views/RiscoView';
import { EstadoView } from './views/EstadoView';
import { PrevisaoView } from './views/PrevisaoView';
import { EvidenciaView } from './views/EvidenciaView';
import { LedgerView } from './views/LedgerView';
import { SaudeView } from './views/SaudeView';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<RiscoView />} />
            <Route path="/estado" element={<EstadoView />} />
            <Route path="/previsao" element={<PrevisaoView />} />
            <Route path="/evidencia" element={<EvidenciaView />} />
            <Route path="/ledger" element={<LedgerView />} />
            <Route path="/saude" element={<SaudeView />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
