import { useMemo, useState } from 'react';
import { useReferences } from '../api/hooks';
import { QueryState } from '../components/QueryState';
import type { ReferencePerson, ReferenceSchool, ReferenceStatus } from '../api/types';
import { View } from '../components/ui';
import './ReferenciasView.css';

const STATUS_LABEL: Record<ReferenceStatus, string> = {
  core: 'core — leitura obrigatoria',
  supporting: 'supporting — consultar em construcao',
  context: 'context — enquadramento',
};

const STATUS_ORDER: ReferenceStatus[] = ['core', 'supporting', 'context'];

function normalize(s: string): string {
  return s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
}

function personMatchesQuery(person: ReferencePerson, q: string): boolean {
  if (!q) return true;
  const hay = normalize(
    [person.name, person.affiliation ?? '', person.resolve, person.work ?? ''].join(' '),
  );
  return hay.includes(normalize(q));
}

/**
 * Cartao de pessoa. O campo `resolve` (por que a referencia existe no
 * projeto) e o CONTEUDO PRINCIPAL — nome/afiliacao sao cabecalho, nao o
 * ponto central. Nunca genero: substantivo de papel/funcao, nunca
 * pronome ou construcao "o/a pesquisador(a)".
 */
function PersonCard({ person, id }: { person: ReferencePerson; id?: string }) {
  return (
    <article id={id} className={`ref-person ref-person--${person.status}`}>
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

function SchoolGroup({
  school,
  statusFilter,
  query,
}: {
  school: ReferenceSchool;
  statusFilter: ReferenceStatus | 'all';
  query: string;
}) {
  const people = school.people
    .filter((p) => statusFilter === 'all' || p.status === statusFilter)
    .filter((p) => personMatchesQuery(p, query));
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
          <PersonCard key={p.id} person={p} id={`pessoa-${p.id}`} />
        ))}
      </div>
    </section>
  );
}

export function ReferenciasView() {
  const { data, isLoading, isError } = useReferences();
  const [statusFilter, setStatusFilter] = useState<ReferenceStatus | 'all'>('all');
  const [layerFilter, setLayerFilter] = useState<string>('all');
  const [query, setQuery] = useState('');

  const peopleById = useMemo(() => {
    const map = new Map<string, ReferencePerson>();
    (data?.schools ?? []).forEach((s) => s.people.forEach((p) => map.set(p.id, p)));
    return map;
  }, [data]);

  const readingOrderPeople = useMemo(
    () => (data?.reading_order ?? []).map((id) => peopleById.get(id)).filter((p): p is ReferencePerson => !!p),
    [data, peopleById],
  );

  const layers = useMemo(() => {
    const set = new Set<string>();
    (data?.schools ?? []).forEach((s) => set.add(s.layer));
    return Array.from(set).sort();
  }, [data]);

  const visibleSchools = useMemo(
    () => (data?.schools ?? []).filter((s) => layerFilter === 'all' || s.layer === layerFilter),
    [data, layerFilter],
  );

  const totalMatches = useMemo(() => {
    let n = 0;
    visibleSchools.forEach((s) => {
      s.people.forEach((p) => {
        if ((statusFilter === 'all' || p.status === statusFilter) && personMatchesQuery(p, query)) n += 1;
      });
    });
    return n;
  }, [visibleSchools, statusFilter, query]);

  const adversarial = data?.adversarial ?? [];

  return (
    <View
      title="Referencias"
      intro="Catalogo de leitura. Cada entrada existe porque resolve uma lacuna nomeada da engine — sem lacuna nomeada, a entrada nao entra."
    >
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

            <div className="ref-toolbar">
              <input
                type="search"
                className="ref-search"
                placeholder="buscar por nome, afiliacao, resolve ou obra..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                aria-label="buscar referencias"
              />
              <span className="footnote ref-toolbar__count mono">
                {totalMatches} de {data.schools.reduce((n, s) => n + s.people.length, 0)} pessoas
              </span>
            </div>

            <div className="ref-filter-row">
              <span className="footnote">status:</span>
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

            <div className="ref-filter-row">
              <span className="footnote">camada da engine:</span>
              <button
                type="button"
                className={`ref-filter-btn${layerFilter === 'all' ? ' ref-filter-btn--active' : ''}`}
                onClick={() => setLayerFilter('all')}
                aria-pressed={layerFilter === 'all'}
              >
                todas
              </button>
              {layers.map((l) => (
                <button
                  key={l}
                  type="button"
                  className={`ref-filter-btn${layerFilter === l ? ' ref-filter-btn--active' : ''}`}
                  onClick={() => setLayerFilter(l)}
                  aria-pressed={layerFilter === l}
                >
                  {l}
                </button>
              ))}
            </div>

            <div className="ref-schools">
              {visibleSchools.map((s) => (
                <SchoolGroup key={s.id} school={s} statusFilter={statusFilter} query={query} />
              ))}
              {visibleSchools.every(
                (s) =>
                  s.people.filter(
                    (p) => (statusFilter === 'all' || p.status === statusFilter) && personMatchesQuery(p, query),
                  ).length === 0,
              ) && <p className="muted">Nenhuma referencia bate com a busca/filtro atual.</p>}
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
                          <td className="ref-precedents__ours">{prec.ours}</td>
                          <td className="ref-precedents__established">{prec.established}</td>
                          <td>
                            {person ? (
                              <a href={`#pessoa-${person.id}`} className="ref-precedents__link">
                                {person.name}
                              </a>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td className="footnote">{prec.note ?? ''}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>

            {adversarial.length > 0 && (
              <section className="ref-adversarial">
                <h3 className="tick-rule">Leituras adversariais</h3>
                <p className="muted">
                  Trabalho que, se estiver certo, ENFRAQUECE uma premissa do projeto. Listado aqui
                  como defesa contra so ler quem concorda.
                </p>
                <div className="ref-adversarial__grid">
                  {adversarial.map((item, i) => {
                    const person = item.by ? peopleById.get(item.by) : null;
                    return (
                      <article key={i} className="ref-adversarial__card">
                        <p className="ref-adversarial__claim">
                          <span className="ref-adversarial__label">premissa questionada</span>
                          {item.claim}
                        </p>
                        <p className="ref-adversarial__challenge">
                          <span className="ref-adversarial__label">contestacao</span>
                          {item.challenge}
                        </p>
                        <p className="ref-adversarial__consequence">
                          <span className="ref-adversarial__label">consequencia se procede</span>
                          {item.consequence}
                        </p>
                        <footer className="footnote ref-adversarial__by">
                          {person ? (
                            <a href={`#pessoa-${person.id}`} className="ref-precedents__link">
                              {person.name}
                            </a>
                          ) : (
                            item.by ?? 'fonte nao catalogada'
                          )}
                        </footer>
                      </article>
                    );
                  })}
                </div>
              </section>
            )}
          </>
        )}
      </QueryState>
    </View>
  );
}
