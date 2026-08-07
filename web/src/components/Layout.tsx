import { NavLink, Outlet } from 'react-router-dom';
import { useAppState } from '../api/hooks';
import './Layout.css';

const ROUTES = [
  { to: '/', label: 'Risco' },
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

export function Layout() {
  return (
    <>
      <header className="app-header">
        <h1 className="app-header__title">Central de Risco Climatico RS</h1>
        <nav className="app-nav">
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
      <footer className="app-footer footnote">
        Instrumento de leitura, nao produto SaaS. Rede de estacoes RS — escala divergente de anomalia.
      </footer>
    </>
  );
}
