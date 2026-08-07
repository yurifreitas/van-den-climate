import { useMemo, useState } from 'react';
import type { ReactNode, CSSProperties } from 'react';
import './ui.css';

/**
 * Primitivas de UI — o contrato de composicao do front.
 *
 * Por que existem: cada visao vinha remontando a mesma casca (`section.view`
 * + `header.view__header` + `div.panel` + grid ad-hoc), e cada uma derivava
 * um pouco. Isso nao escala: o sistema de design vira sugestao.
 *
 * Regra de uso:
 *   1. Visao = <View> com <Section> dentro; nunca `<section className="view">`.
 *   2. Painel = <Panel>; nunca `<div className="panel">`.
 *   3. Espaco so via `gap` das primitivas (escala 1/2/3/4/6/8/12).
 *   4. Se voce precisou de `style={{...}}` de layout, falta uma primitiva —
 *      adicione aqui, nao no arquivo da visao.
 *   5. Nenhuma primitiva aceita cor: cor e exclusividade do dado
 *      (theme/chartColors.ts). Ver DESIGN.md §1.
 */

type Gap = 1 | 2 | 3 | 4 | 6 | 8 | 12;

/* ------------------------------------------------------------------ layout */

export function Stack({
  children,
  gap = 3,
  dir = 'col',
  className = '',
  ...rest
}: {
  children: ReactNode;
  gap?: Gap;
  dir?: 'col' | 'row';
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <div className={`ui-stack ${className}`} data-dir={dir} data-gap={gap} {...rest}>
      {children}
    </div>
  );
}

/** Grade responsiva; `min` e a largura minima do cartao antes de quebrar. */
export function Grid({
  children,
  min = 280,
  className = '',
}: {
  children: ReactNode;
  min?: number;
  className?: string;
}) {
  return (
    <div
      className={`ui-grid ${className}`}
      style={{ '--ui-grid-min': `${min}px` } as CSSProperties}
    >
      {children}
    </div>
  );
}

/** Titulo a esquerda, acoes a direita. Usada em barra de painel e de visao. */
export function Row({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`ui-row ${className}`}>{children}</div>;
}

/* ----------------------------------------------------------------- estrutura */

/** Casca de rota: titulo, uma linha do que a visao responde, acoes opcionais. */
export function View({
  title,
  intro,
  actions,
  children,
}: {
  title: string;
  intro: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="ui-view">
      <header className="ui-view__header">
        <Row>
          <div>
            <h2 className="t-display">{title}</h2>
            <p className="ui-view__intro t-small">{intro}</p>
          </div>
          {actions}
        </Row>
      </header>
      {children}
    </section>
  );
}

/**
 * Grupo dentro da visao. `note` e aparato tecnico (mono, discreto) e fica
 * ACIMA do conteudo — limitacao de metodo se le antes do numero, nao depois.
 */
export function Section({
  title,
  note,
  actions,
  rule = true,
  children,
}: {
  title?: string;
  note?: ReactNode;
  actions?: ReactNode;
  rule?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="ui-section" data-rule={rule ? 'line' : 'none'}>
      {title && (
        <Row className="ui-section__title">
          <h3 className="t-section">{title}</h3>
          {actions}
        </Row>
      )}
      {note && <p className="t-note">{note}</p>}
      {children}
    </div>
  );
}

/**
 * Superficie de elevacao 1. `tone`:
 *   default  — carta com borda
 *   quiet    — sem fundo (agrupa sem competir)
 *   verdict  — borda tracejada: resultado de criterio, nao dado observado
 */
export function Panel({
  title,
  actions,
  footnote,
  tone,
  pad,
  children,
}: {
  title?: string;
  actions?: ReactNode;
  footnote?: ReactNode;
  tone?: 'quiet' | 'verdict';
  pad?: 'tight' | 'none';
  children: ReactNode;
}) {
  return (
    <div className="ui-panel" data-tone={tone} data-pad={pad}>
      {(title || actions) && (
        <Row>
          {title ? <h4 className="t-section">{title}</h4> : <span />}
          {actions}
        </Row>
      )}
      {children}
      {footnote && <p className="t-note">{footnote}</p>}
    </div>
  );
}

/* -------------------------------------------------------------------- dado */

/** Numero-manchete. `value` ausente vira "—", nunca 0 (DESIGN.md §5). */
export function Metric({
  value,
  label,
  digits = 2,
}: {
  value: number | string | null | undefined;
  label: ReactNode;
  digits?: number;
}) {
  const shown =
    value === null || value === undefined || value === ''
      ? '—'
      : typeof value === 'number'
        ? value.toFixed(digits)
        : value;
  return (
    <p className="ui-metric">
      <span className="t-hero ui-metric__value">{shown}</span>
      <span className="t-small ui-metric__label">{label}</span>
    </p>
  );
}

/** Rotulo + controle. Mantem o alvo de toque de 44px no mobile. */
export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="ui-field t-small">
      {label}
      {children}
    </label>
  );
}

/** Vazio: o que falta e o que destrava. Nunca ilustracao (DESIGN.md §6). */
export function Empty({ children }: { children: ReactNode }) {
  return <p className="ui-empty t-small">{children}</p>;
}

/**
 * Tabela de dados declarativa — a marca mais repetida do front.
 *
 * Substitui o par `div.scroll-x > table.data-table` remontado a mao em cada
 * visao: rolagem, cabecalho fixo, zebra, numerais tabulares e ordenacao
 * ficam num lugar so. Coluna com `sortable` ganha o botao de ordenar e o
 * `aria-sort` correto sem a visao guardar estado.
 *
 * `align: 'num'` aplica a classe mono/tabular — todo numero passa por aqui.
 */
export type Column<T> = {
  key: string;
  header: ReactNode;
  /** Valor exibido. Devolva '—' para ausente — nunca 0 (DESIGN.md §5). */
  cell: (row: T) => ReactNode;
  align?: 'text' | 'num';
  /** Valor bruto para ordenacao; presenca torna a coluna ordenavel. */
  sortValue?: (row: T) => string | number;
  title?: (row: T) => string | undefined;
};

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  defaultSort,
  empty = 'Sem linhas.',
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string | number;
  defaultSort?: { key: string; dir: 'asc' | 'desc' };
  empty?: ReactNode;
}) {
  const [sort, setSort] = useState(defaultSort);

  const sorted = useMemo(() => {
    const col = sort && columns.find((c) => c.key === sort.key);
    if (!col?.sortValue) return rows;
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = col.sortValue!(a);
      const bv = col.sortValue!(b);
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sort!.dir === 'asc' ? cmp : -cmp;
    });
    return copy;
  }, [rows, columns, sort]);

  const toggle = (key: string) =>
    setSort((s) =>
      s && s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'asc' },
    );

  if (rows.length === 0) return <Empty>{empty}</Empty>;

  return (
    <div className="scroll-x">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((c) => {
              const active = sort?.key === c.key;
              return (
                <th
                  key={c.key}
                  aria-sort={
                    c.sortValue
                      ? active
                        ? sort!.dir === 'asc'
                          ? 'ascending'
                          : 'descending'
                        : 'none'
                      : undefined
                  }
                >
                  {c.sortValue ? (
                    <button type="button" className="th-sort-btn" onClick={() => toggle(c.key)}>
                      {c.header} {active ? (sort!.dir === 'asc' ? '↑' : '↓') : ''}
                    </button>
                  ) : (
                    c.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr key={rowKey(row, i)}>
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={c.align === 'num' ? 'num' : undefined}
                  title={c.title?.(row)}
                >
                  {c.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
