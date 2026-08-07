import { useHealthBreaks, useHealthCoverage, useHealthSources } from '../api/hooks';
import { QueryState } from '../components/QueryState';
import './views.css';

const STATUS_LABEL: Record<string, string> = { ok: 'ok', stale: 'desatualizado', failed: 'falhou' };

/**
 * Rota `/saude` — pergunta: "a rede de estacoes tem cobertura suficiente,
 * onde ha quebras de homogeneidade, e as fontes de ingestao estao vivas?"
 *
 * Fonte que falhou vira LACUNA DECLARADA na tabela (status "falhou"), nunca
 * uma excecao silenciosa que derruba a tela (regra 3 do contrato).
 */
export function SaudeView() {
  const coverage = useHealthCoverage();
  const breaks = useHealthBreaks();
  const sources = useHealthSources();

  return (
    <section>
      <h2>Saude dos dados</h2>

      <div className="panel">
        <h3>Status das fontes</h3>
        <QueryState isLoading={sources.isLoading} isError={sources.isError}>
          <div className="scroll-x">
            <table className="data-table">
              <thead>
                <tr>
                  <th>fonte</th>
                  <th>ultima ingestao</th>
                  <th>linhas</th>
                  <th>hash</th>
                  <th>status</th>
                </tr>
              </thead>
              <tbody>
                {sources.data?.sources.map((s) => (
                  <tr key={s.source_id}>
                    <td className="num">{s.source_id}</td>
                    <td className="num">{s.last_ingested_at ?? '— (lacuna declarada)'}</td>
                    <td className="num">{s.rows ?? '—'}</td>
                    {/* hash completo e ilegivel na tabela; os 12 primeiros
                        caracteres ja identificam o download de forma unica */}
                    <td className="num" title={s.sha256 ?? ''}>{s.sha256?.slice(0, 12) ?? '—'}</td>
                    <td className="num">{STATUS_LABEL[s.status]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </QueryState>
      </div>

      <div className="panel">
        <h3>Cobertura — estacao x ano</h3>
        <QueryState isLoading={coverage.isLoading} isError={coverage.isError}>
          <div className="scroll-x">
            <table className="data-table">
              <thead>
                <tr>
                  <th>estacao</th>
                  <th>ano</th>
                  <th>cobertura</th>
                </tr>
              </thead>
              <tbody>
                {coverage.data?.cells.map((c, i) => (
                  <tr key={i}>
                    <td>{c.label}</td>
                    <td className="num">{c.year}</td>
                    <td className="num">{(c.coverage * 100).toFixed(0)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </QueryState>
      </div>

      <div className="panel">
        <h3>Quebras de homogeneidade</h3>
        <QueryState isLoading={breaks.isLoading} isError={breaks.isError}>
          <div className="scroll-x">
            <table className="data-table">
              <thead>
                <tr>
                  <th>estacao</th>
                  <th>detectada em</th>
                  <th>descricao</th>
                </tr>
              </thead>
              <tbody>
                {breaks.data?.breaks.map((b, i) => (
                  <tr key={i}>
                    <td>{b.label}</td>
                    <td className="num">{b.detected_at}</td>
                    <td>{b.description}</td>
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
