import { NavLink, Outlet } from 'react-router-dom';
import './Layout.css';

const ROUTES = [
  { to: '/', label: 'Risco' },
  { to: '/estado', label: 'Estado' },
  { to: '/previsao', label: 'Previsao' },
  { to: '/evidencia', label: 'Evidencia' },
  { to: '/ledger', label: 'Ledger' },
  { to: '/saude', label: 'Saude' },
];

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
      </header>
      <main className="app-main">
        <Outlet />
      </main>
      <footer className="app-footer muted">
        Instrumento de leitura, nao produto SaaS. Rede de estacoes RS — escala divergente de anomalia.
      </footer>
    </>
  );
}
