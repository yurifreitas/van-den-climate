import { NavLink, Outlet } from 'react-router-dom';
import { MODO_ESTATICO } from '../api/client';
import { useAppState, useMeta } from '../api/hooks';
import './Layout.css';

const ROUTES = [
  { to: '/', label: 'Risco' },
  { to: '/plano', label: 'Plano' },
  { to: '/municipios', label: 'Municipios' },
  { to: '/resposta', label: 'Resposta' },
  { to: '/historico', label: 'Historico' },
  { to: '/estado', label: 'Estado' },
  { to: '/previsao', label: 'Previsao' },
  { to: '/evidencia', label: 'Evidencia' },
  { to: '/ledger', label: 'Ledger' },
  { to: '/saude', label: 'Saude' },
  { to: '/referencias', label: 'Referencias' },
];

/**
 * Indicador de estado do sistema na barra superior fixa (prioridade 5 do
 * refino visual): ONI atual e classificacao, buscados de /state. Usa
 * SOMENTE giz/bruma — o numero e dado climatico mas este e um indicador de
 * NAVEGACAO, nao um grafico de anomalia; a regra de exclusividade de
 * FRIO/QUENTE e para elementos de UI, e uma pilula de status na topbar e UI.
 */
function SystemStateIndicator() {
  const { data, isLoading, isError } = useAppState();

  if (isLoading) {
    return <span className="skeleton system-state__skeleton" aria-label="carregando estado do sistema" />;
  }
  if (isError || !data || data.headline.oni === null || data.headline.oni === undefined) {
    return <span className="system-state system-state--absent">ONI indisponivel</span>;
  }
  return (
    <span className="system-state" title={`Atualizado em ${data.as_of}`}>
      <span className="system-state__label">ONI</span>
      <span className="system-state__value mono">{data.headline.oni.toFixed(2)}</span>
      <span className="system-state__classification">{data.headline.classification}</span>
    </span>
  );
}

/**
 * Faixa da demo estatica.
 *
 * Existe pela mesma razao que todo selo de proveniencia neste projeto: um
 * numero congelado que se apresenta como atual e a falha mais cara possivel
 * numa central de risco — pior que a tela vazia que ele substitui. A demo
 * publica do GitHub Pages mostra dados de uma data especifica e precisa dizer
 * qual, no topo, antes de qualquer numero.
 *
 * A data vem do carimbo `_snapshot` que o gerador poe em toda resposta, e nao
 * de uma constante de build: assim ela nao pode ficar velha sem que o dado ao
 * lado tenha ficado velho junto.
 */
function FaixaEstatica() {
  const { data } = useMeta();
  if (!MODO_ESTATICO) return null;
  const capturado = (data as { _snapshot?: { capturado_em?: string } } | undefined)?._snapshot
    ?.capturado_em;
  return (
    <div className="app-demo" role="note">
      <strong>Demo estatica.</strong> Os dados sao uma fotografia
      {capturado ? ` de ${capturado.slice(0, 10)}` : ''} e nao se atualizam sozinhos. Para dados
      vivos, rode a API local — veja o README.
    </div>
  );
}

export function Layout() {
  return (
    <>
      <FaixaEstatica />
      <header className="app-header">
        <span className="app-header__brand">
          <span className="app-header__mark" aria-hidden="true" />
          Central de Risco Climatico RS
        </span>
        <nav className="app-nav" aria-label="rotas principais">
          {ROUTES.map((r) => (
            <NavLink
              key={r.to}
              to={r.to}
              end={r.to === '/'}
              className={({ isActive }) => `app-nav__link${isActive ? ' app-nav__link--active' : ''}`}
            >
              {r.label}
            </NavLink>
          ))}
        </nav>
        <SystemStateIndicator />
      </header>
      <main className="app-main">
        <Outlet />
      </main>
      <footer className="app-footer t-note">
        Instrumento de leitura, nao produto SaaS. Rede de estacoes RS — escala divergente de anomalia.
      </footer>
    </>
  );
}
