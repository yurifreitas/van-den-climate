import { useMemo } from 'react';
import type { CoverageCell } from '../api/types';
import './CoverageMatrix.css';

/**
 * Matriz sinal x ano — uma celula por ano, opacidade = fracao de cobertura.
 *
 * Por que nao tabela: sao ~500 linhas. Tabela responde "qual a cobertura de
 * X em 1987?", mas a pergunta real da tela e outra — "onde estao os buracos,
 * e desde quando cada serie existe?". Isso e uma pergunta de FORMA, e a
 * resposta se le num golpe de vista numa matriz e nunca numa lista.
 *
 * Escala em giz, nao em frio/quente: cobertura de dado nao e anomalia, e as
 * duas cores divergentes pertencem exclusivamente ao dado climatico.
 */
export function CoverageMatrix({ cells }: { cells: CoverageCell[] }) {
  const { rows, years } = useMemo(() => {
    const byId = new Map<string, Map<number, number>>();
    let min = Infinity;
    let max = -Infinity;
    for (const c of cells) {
      if (!byId.has(c.station_id)) byId.set(c.station_id, new Map());
      byId.get(c.station_id)!.set(c.year, c.coverage_frac);
      if (c.year < min) min = c.year;
      if (c.year > max) max = c.year;
    }
    const ys: number[] = [];
    for (let y = min; y <= max; y += 1) ys.push(y);
    return {
      rows: [...byId.entries()].sort(([a], [b]) => a.localeCompare(b)),
      years: Number.isFinite(min) ? ys : [],
    };
  }, [cells]);

  if (!rows.length) return null;

  // Décadas como marcas de escala — o eixo inteiro seria ilegível a 1 célula
  // por ano, e a década é a unidade em que se lê "desde quando existe".
  const ticks = years.filter((y) => y % 10 === 0);

  return (
    <div className="cov">
      <div className="cov__grid">
        {rows.map(([id, byYear]) => (
          <div className="cov__row" key={id}>
            <span className="cov__label mono">{id}</span>
            <div className="cov__track">
              {years.map((y) => {
                const f = byYear.get(y);
                return (
                  <i
                    key={y}
                    className={f === undefined ? 'cov__cell cov__cell--gap' : 'cov__cell'}
                    style={f === undefined ? undefined : { opacity: 0.18 + f * 0.82 }}
                    title={`${id} · ${y} · ${
                      f === undefined ? 'sem dado' : `${Math.round(f * 100)}%`
                    }`}
                  />
                );
              })}
            </div>
          </div>
        ))}
        <div className="cov__row cov__row--axis">
          <span className="cov__label" />
          <div className="cov__track">
            {years.map((y) => (
              <i className="cov__tick" key={y}>
                {ticks.includes(y) ? <span className="cov__tick-label mono">{y}</span> : null}
              </i>
            ))}
          </div>
        </div>
      </div>
      <p className="t-note">
        Opacidade = fração do ano com observação. Célula vazada = sem dado.
        {' '}O ONI cobre desde 1950; o SAM só a partir de 1979 — é essa diferença
        que limita a âncora de calibração.
      </p>
    </div>
  );
}
