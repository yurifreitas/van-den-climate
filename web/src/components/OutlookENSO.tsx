import { useEnsoOutlook } from '../api/hooks';
import { ProvenanceBadge } from './ProvenanceBadge';
import { Empty, Panel, Row, Stack } from './ui';
import './OutlookENSO.css';

/**
 * Boletim ENSO do CPC/NOAA — a unica camada prospectiva da central.
 *
 * A decisao de desenho mais importante aqui e a atribuicao. O painel diz, no
 * cabecalho e no rodape, que a previsao e do CPC e que a engine local NAO tem
 * previsao aceita. Numa central construida para separar o que sabe do que
 * supoe, deixar o usuario acreditar que a probabilidade de 81% saiu daqui
 * seria a falha mais cara possivel — mais cara que nao mostrar o boletim.
 *
 * Por isso o bloco "esta engine" fica lado a lado com o bloco "CPC/NOAA", e
 * nao escondido num rodape: a comparacao e o conteudo.
 */
export function OutlookENSO() {
  const { data, isLoading, isError } = useEnsoOutlook();

  if (isLoading) {
    return (
      <Panel title="Outlook ENSO">
        <span className="skeleton outlook__skeleton" aria-label="carregando boletim" />
      </Panel>
    );
  }

  if (isError || !data?.disponivel) {
    return (
      <Panel title="Outlook ENSO">
        <Empty>
          {data?.motivo ?? 'Boletim do CPC indisponivel.'} Sem ele a central continua funcionando —
          o risco estrutural nao depende de previsao.
        </Empty>
      </Panel>
    );
  }

  const desatualizado =
    data.next_update !== null &&
    data.next_update !== undefined &&
    new Date(data.next_update) < new Date();

  return (
    <Panel
      title="Outlook ENSO — CPC/NOAA"
      actions={<ProvenanceBadge basis={data.basis ?? 'modeled'} />}
      footnote={
        <>
          {data.autoria} Emitido em {data.issued}
          {data.next_update && ` · proximo boletim ${data.next_update}`}
          {desatualizado && ' · ATRASADO em relacao ao cronograma do CPC'}
          {'. '}
          <a href={data.source_url} target="_blank" rel="noreferrer noopener">
            boletim original
          </a>
        </>
      }
    >
      <Row>
        <span className="outlook__status">{data.alert_status}</span>
        <span className="t-note">{data.horizonte?.fonte_prospectiva}</span>
      </Row>

      <p className="outlook__synopsis t-body">{data.synopsis}</p>

      <div className="outlook__probs">
        {(data.probabilities ?? []).map((p) => (
          <div key={`${p.percent}-${p.claim}`} className="outlook__prob">
            <span className="t-hero outlook__pct">{p.percent}%</span>
            <span className="t-small">{p.claim}</span>
          </div>
        ))}
      </div>

      {/* A parede de skill. Nao e rodape: e o que responde "e 2027?" */}
      <div className="outlook__horizonte">
        <Stack gap={2}>
          <span className="t-section">Ate onde essa previsao vale</span>
          <p className="t-small">
            Horizonte util de previsao ENSO: ~{data.horizonte?.limite_util_meses} meses.{' '}
            {data.horizonte?.barreira}.
          </p>
          <p className="t-small outlook__consequencia">{data.horizonte?.consequencia}</p>
        </Stack>
      </div>

      {/* Lado a lado com o outlook externo, de proposito. */}
      <div className="outlook__local">
        <span className="t-section">Esta engine</span>
        <p className="t-small">
          <strong>Sem previsao aceita.</strong> {data.engine_local?.motivo}. O boletim acima e
          contexto externo (ADR-012) e nao alimenta nenhum bloco de feature.
        </p>
      </div>
    </Panel>
  );
}
