import { useMemo, useState } from 'react';
import { useReferences } from '../api/hooks';
import { QueryState } from '../components/QueryState';
import type { ReferencePerson, ReferenceSchool, ReferenceStatus } from '../api/types';
import './ReferenciasView.css';

const STATUS_LABEL: Record<ReferenceStatus, string> = {
  core: 'core — leitura obrigatoria',
  supporting: 'supporting — consultar em construcao',
  context: 'context — enquadramento',
};

const STATUS_ORDER: ReferenceStatus[] = ['core', 'supporting', 'context'];

/**
 * Cartao de pessoa. O campo `resolve` (por que a referencia existe no
 * projeto) e o CONTEUDO PRINCIPAL — nome/afiliacao sao cabecalho, nao o
 * ponto central. Nunca genero: substantivo de papel/funcao, nunca
 * pronome ou construcao "o/a pesquisador(a)".
 */
function PersonCard({ person }: { person: ReferencePerson }) {
  return (
    <article className={`ref-person ref-person--${person.status}`}>
      <header className="ref-person__header">
        <h4 className="ref-person__name">{person.name}</h4>
        <span className={`ref-status-badge ref-status-badge--${person.status}`}>{person.status}</span>
      </header>
      {person.affiliation && <p className="ref-person__affiliation footnote">{person.affiliation}</p>}
      <p className="ref-person__resolve">{person.resolve}</p>
      {person.work && <p className="ref-person__work footnote">obra: {person.work}</p>}
    </article>
  );
}

function SchoolGroup({ school, statusFilter }: { school: ReferenceSchool; statusFilter: ReferenceStatus | 'all' }) {
  const people = statusFilter === 'all' ? school.people : school.people.filter((p) => p.status === statusFilter);
  if (people.length === 0) return null;
  return (
    <section className="ref-school">
      <header className="ref-school__header">
        <div className="ref-school__title-row">
          <h3 className="ref-school__label">{school.label}</h3>
          <span className="footnote ref-school__layer">{school.layer}</span>
        </div>
        <p className="ref-school__why">{school.why}</p>
      </header>
      <div className="ref-school__grid">
        {people.map((p) => (
          <PersonCard key={p.id} person={p} />
        ))}
      </div>
    </section>
  );
}

export function ReferenciasView() {
  const { data, isLoading, isError } = useReferences();
  const [statusFilter, setStatusFilter] = useState<ReferenceStatus | 'all'>('all');

  const peopleById = useMemo(() => {
    const map = new Map<string, ReferencePerson>();
    (data?.schools ?? []).forEach((s) => s.people.forEach((p) => map.set(p.id, p)));
    return map;
  }, [data]);

  const readingOrderPeople = useMemo(
    () => (data?.reading_order ?? []).map((id) => peopleById.get(id)).filter((p): p is ReferencePerson => !!p),
    [data, peopleById],
  );

  return (
    <section>
      <h2>Referencias — catalogo de leitura</h2>
      <p className="muted">
        Cada entrada existe porque resolve uma lacuna nomeada da engine. Sem lacuna nomeada, a
        entrada nao entra no catalogo.
      </p>

      <QueryState isLoading={isLoading} isError={isError}>
        {data && (
          <>
            <section className="ref-reading-order">
              <h3 className="ref-reading-order__title tick-rule">Trilha de leitura — ordem por retorno imediato</h3>
              <ol className="ref-reading-order__list">
                {readingOrderPeople.map((p, i) => (
                  <li key={p.id} className="ref-reading-order__item">
                    <span className="ref-reading-order__index mono">{String(i + 1).padStart(2, '0')}</span>
                    <div>
                      <p className="ref-reading-order__name">{p.name}</p>
                      <p className="ref-reading-order__resolve">{p.resolve}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </section>

            <div className="ref-filter-row">
              <span className="footnote">filtrar por status:</span>
              {(['all', ...STATUS_ORDER] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  className={`ref-filter-btn${statusFilter === s ? ' ref-filter-btn--active' : ''}`}
                  onClick={() => setStatusFilter(s)}
                  aria-pressed={statusFilter === s}
                >
                  {s === 'all' ? 'todos' : STATUS_LABEL[s]}
                </button>
              ))}
            </div>

            <div className="ref-schools">
              {data.schools.map((s) => (
                <SchoolGroup key={s.id} school={s} statusFilter={statusFilter} />
              ))}
            </div>

            <section className="ref-precedents">
              <h3 className="tick-rule">Precedentes de metodo</h3>
              <p className="muted">Onde uma ideia do projeto ja existe, nomeada, na literatura.</p>
              <div className="scroll-x">
                <table className="data-table ref-precedents__table">
                  <thead>
                    <tr>
                      <th>Nossa ideia</th>
                      <th>Nome estabelecido</th>
                      <th>Referencia</th>
                      <th>Nota</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.precedents.map((prec, i) => {
                      const person = prec.by ? peopleById.get(prec.by) : null;
                      return (
                        <tr key={i}>
                          <td>{prec.ours}</td>
                          <td>{prec.established}</td>
                          <td>{person ? person.name : '—'}</td>
                          <td className="footnote">{prec.note ?? ''}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </QueryState>
    </section>
  );
}
