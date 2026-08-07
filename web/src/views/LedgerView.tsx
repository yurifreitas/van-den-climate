import { useLedger, useLedgerSkill } from '../api/hooks';
import { QueryState } from '../components/QueryState';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import './views.css';

/** Metrica ausente e "—", nunca 0 nem tela quebrada. */
const num = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : v.toFixed(3);

const TERCIL = ['Abaixo', 'Perto', 'Acima'];

/**
 * Rota `/ledger` — pergunta: "o que foi previsto de fato, o que foi
 * observado, e qual o skill medido com incerteza (nao um numero solto)?"
 * Ledger e imutavel (append-only, contrato §4) — por isso e tabela, nao
 * grafico editavel.
 */
export function LedgerView() {
  const ledger = useLedger();
  const skill = useLedgerSkill();

  return (
    <section>
      <h2>Ledger — previsto vs observado</h2>

      <div className="panel">
        <div className="section-title-row">
          <h3>Skill (RPSS/BSS)</h3>
          {skill.data && <ProvenanceBadge basis={skill.data.provenance.basis} />}
        </div>
        <QueryState isLoading={skill.isLoading} isError={skill.isError}>
          <div className="scroll-x">
            <table className="data-table">
              <thead>
                <tr>
                  <th>metrica</th>
                  <th>ponto</th>
                  <th>IC90</th>
                  <th>nulo de permutacao</th>
                </tr>
              </thead>
              <tbody>
                {/* `num(...)` em vez de `.toFixed()` direto: com nenhum modelo
                    aceito sob a ADR-007, a API devolve `null` — que e o
                    RESULTADO correto, nao ausencia de dado. Chamar .toFixed()
                    em null derrubava a tela justamente no estado que o projeto
                    considera certo. */}
                {skill.data?.metrics.map((m) => (
                  <tr key={m.metric}>
                    <td>{m.metric}</td>
                    <td className="num">{num(m.point)}</td>
                    <td className="num">[{num(m.lo)}, {num(m.hi)}]</td>
                    <td className="num">{num(m.permutation_null)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </QueryState>
      </div>

      <div className="panel">
        <h3>Previsoes emitidas (append-only)</h3>
        <QueryState isLoading={ledger.isLoading} isError={ledger.isError}>
          <div className="scroll-x">
            <table className="data-table">
              <thead>
                <tr>
                  <th>alvo</th>
                  <th>emitido em</th>
                  <th>previsto</th>
                  <th>observado</th>
                </tr>
              </thead>
              <tbody>
                {ledger.data?.entries.map((e, i) => (
                  <tr key={i}>
                    <td>{e.target_id}</td>
                    <td className="num">{e.issued_at}</td>
                    <td className="num">{TERCIL[e.predicted_tercile]}</td>
                    <td className="num">{e.observed_tercile === null ? '—' : TERCIL[e.observed_tercile]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </QueryState>
      </div>
    </section>
  );
}
