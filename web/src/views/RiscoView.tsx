import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import type { CSSProperties } from 'react';
import {
  useAppState,
  useEnsoOutlook,
  useHazardsCatalog,
  useMalhaMunicipal,
  useMunicipalRisk,
  usePlano,
} from '../api/hooks';
import { HazardCard } from '../components/HazardCard';
import { MapaMunicipal } from '../components/MapaMunicipal';
import { MapaTeleconexao } from '../components/MapaTeleconexao';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { QueryState } from '../components/QueryState';
import { View, Section, Grid, Empty, Panel, Stack } from '../components/ui';
import { NIVEL, NIVEL_LABEL } from '../theme/palette';
import './RiscoView.css';

/** Ano do dado em tela, nao do relogio: o titulo tem de acompanhar o dado. */
const ANO_CORRENTE = new Date().getFullYear();

const HORIZON_LABEL: Record<string, string> = {
  seasonal: 'Sazonal (OND) — desloca probabilidade de fundo',
  subseasonal: 'Sub-sazonal (2-6 semanas) — janelas via MJO/regime',
  synoptic: 'Sinotico (1-7 dias) — fora de escopo desta engine',
};

/**
 * Camadas da central. A ordem e a de LEITURA, nao a de construcao: comeca em
 * "o que fazer" e termina em "de onde vem o sinal", porque e assim que a
 * pergunta chega — ninguem abre uma central de risco querendo saber do ONI.
 */
const CAMADAS = [
  { to: '/plano', titulo: 'Plano', pergunta: 'O que fazer, onde, e antes de quando' },
  { to: '/municipios', titulo: 'Municipios', pergunta: 'Prioridade preventiva nos 497, com decomposicao' },
  { to: '/recursos', titulo: 'Recursos', pergunta: 'Onde estao os meios de resposta, e onde falta' },
  { to: '/resposta', titulo: 'Resposta', pergunta: 'O depois: vulneraveis, saude, autonomia logistica' },
  { to: '/historico', titulo: 'Historico', pergunta: 'Meio seculo de primaveras — El Nino molha o RS?' },
  { to: '/estado', titulo: 'Estado', pergunta: 'Em que percentil cada modo climatico esta agora' },
  { to: '/previsao', titulo: 'Previsao', pergunta: 'O que a engine sustenta, e o que nao' },
  { to: '/saude', titulo: 'Saude do dado', pergunta: 'Fonte, cobertura e quebra de serie' },
];

export function RiscoView() {
  const { data, isLoading, isError } = useHazardsCatalog();
  const estado = useAppState();
  const outlook = useEnsoOutlook();
  const municipal = useMunicipalRisk('atual');
  const malha = useMalhaMunicipal();
  const plano = usePlano('atual');

  const grouped = data
    ? data.hazards.reduce<Record<string, typeof data.hazards>>((acc, h) => {
        (acc[h.horizon] ??= []).push(h);
        return acc;
      }, {})
    : {};

  const sazonal = data?.hazards.find((h) => h.id === 'seasonal_wet_anomaly');
  const oni = estado.data?.headline.oni ?? null;

  // Probabilidade mais especifica do boletim: a que fala da temporada-alvo.
  const probOND = useMemo(
    () => (outlook.data?.probabilities ?? []).find((p) => /October|December|OND/i.test(p.claim)),
    [outlook.data],
  );

  const nAlto = useMemo(
    () => (municipal.data?.municipios ?? []).filter((m) => m.level === 'high').length,
    [municipal.data],
  );

  const acoesTop = useMemo(
    () =>
      (plano.data?.por_acao ?? [])
        .filter((a) => a.horizonte === 'imediato' && a.n_municipios > 0)
        .sort((a, b) => b.n_municipios - a.n_municipios)
        .slice(0, 5),
    [plano.data],
  );

  return (
    <View
      title="Risco"
      intro="Central de risco climatico do Rio Grande do Sul: onde agir antes da proxima tempestade, com a evidencia de cada afirmacao ao lado dela."
    >
      {/* HERO — o estado agora, antes de qualquer navegacao.
          Uma central de risco cuja primeira pergunta ("estamos em perigo?")
          exige rolar a pagina falhou antes de comecar. */}
      <div className="hero" data-nivel={sazonal?.level ?? undefined}>
        <div className="hero__principal">
          <span className="t-section">Estado do sistema</span>
          <p className="hero__oni">
            <span className="t-hero">{oni === null ? '—' : oni.toFixed(2)}</span>
            <span className="hero__unidade t-small">ONI</span>
          </p>
          <p className="hero__classificacao">
            {estado.data?.headline.classification ?? 'indisponivel'}
          </p>
          <ProvenanceBadge basis="measured" />
        </div>

        <div className="hero__coluna">
          <span className="t-section">Perigo sazonal OND</span>
          {sazonal?.level ? (
            <>
              <p
                className="hero__nivel"
                style={{ '--nivel-cor': NIVEL[sazonal.level as keyof typeof NIVEL] } as CSSProperties}
              >
                {NIVEL_LABEL[sazonal.level as keyof typeof NIVEL]}
              </p>
              {/* NAO repete `sazonal.label` — ele ja aparece no card de perigo
                  mais abaixo, e a mesma frase duas vezes na mesma tela gasta
                  atencao sem acrescentar. Aqui vai o que o nivel SIGNIFICA. */}
              <p className="t-small">
                Desloca probabilidade de fundo para a temporada OND. Nao indica evento individual.
              </p>
              <ProvenanceBadge basis={sazonal.basis} />
            </>
          ) : (
            <span className="skeleton hero__skel" />
          )}
        </div>

        <div className="hero__coluna">
          <span className="t-section">O que o CPC espera</span>
          {probOND ? (
            <>
              <p className="hero__prob">
                <span className="t-hero">{probOND.percent}%</span>
              </p>
              <p className="t-small">{probOND.claim}</p>
              <ProvenanceBadge basis="modeled" />
            </>
          ) : (
            <span className="skeleton hero__skel" />
          )}
          <p className="t-note">
            Previsao do CPC/NOAA, nao desta engine — <Link to="/previsao">por que</Link>
          </p>
        </div>
      </div>

      {/* Numeros que atravessam as camadas. Ficam alto porque respondem
          "qual o tamanho do problema" antes de qualquer mapa. */}
      <div className="numeros">
        <Numero n={municipal.data?.n_total} label="municipios avaliados" para="/municipios" />
        <Numero n={nAlto} label="em nivel ALTO agora" para="/municipios" tom="alerta" />
        <Numero n={plano.data?.n_acoes_total} label="acoes identificadas" para="/plano" />
        <Numero
          n={plano.data?.n_imediatas_total}
          label="cabem antes da primavera"
          para="/plano"
          tom="acento"
        />
      </div>

      {/* Mapa de risco do ano corrente. Vem ANTES da teleconexao: numa central
          de risco a pergunta e "onde", e so depois "por que". */}
      <Section
        title={`Onde esta o risco — ${ANO_CORRENTE}`}
        note={
          municipal.data
            ? `Cenario "agora", ONI medido ${municipal.data.oni?.toFixed(2) ?? '—'}. ` +
              `${municipal.data.n_completo} municipios com base completa. ` +
              'Indice de prioridade preventiva, NAO previsao de cheia.'
            : undefined
        }
        actions={<Link to="/municipios">abrir detalhamento</Link>}
      >
        <Grid min={380}>
          <Panel pad="tight">
            {municipal.data && malha.data ? (
              <MapaMunicipal
                malha={malha.data}
                municipios={municipal.data.municipios}
                camada="risco"
                selecionado={null}
                onSelecionar={() => {}}
              />
            ) : (
              <span className="skeleton" style={{ height: 320, display: 'block' }} />
            )}
          </Panel>
          <Panel title="Prioridade mais alta agora">
            {municipal.data ? (
              <ol className="topo-risco">
                {municipal.data.municipios
                  .filter((m) => m.score !== null)
                  .slice(0, 10)
                  .map((m) => (
                    <li key={m.cod_mun}>
                      <span
                        className="topo-risco__marca"
                        style={{ background: m.level ? NIVEL[m.level] : 'var(--bruma)' }}
                      />
                      <span className="topo-risco__nome">{m.municipio}</span>
                      <span className="t-data">{m.score!.toFixed(1)}</span>
                    </li>
                  ))}
              </ol>
            ) : (
              <span className="skeleton" style={{ height: 240, display: 'block' }} />
            )}
          </Panel>
        </Grid>
      </Section>

      {/* O que fazer. E a culminacao da central e estava a tres cliques. */}
      <Section
        title="O que fazer antes da primavera"
        note="Acoes que cabem em ato administrativo, contrato ou treinamento — nao dependem de obra. Cada uma sai de dado declarado."
        actions={<Link to="/plano">plano completo</Link>}
      >
        {acoesTop.length === 0 ? (
          <span className="skeleton" style={{ height: 120, display: 'block' }} />
        ) : (
          <Stack gap={2}>
            {acoesTop.map((a) => (
              <Link key={a.id} to="/plano" className="acao-home">
                <span className="acao-home__n t-hero">{a.n_municipios}</span>
                <span className="acao-home__texto">
                  <span className="acao-home__titulo">{a.titulo}</span>
                  <span className="t-note">
                    {a.populacao_coberta.toLocaleString('pt-BR')} habitantes · esforco {a.esforco}
                  </span>
                </span>
              </Link>
            ))}
          </Stack>
        )}
      </Section>

      {/* Caminho para a profundidade. Sem isto, oito camadas ficam escondidas
          atras de uma barra de navegacao que nao diz o que cada uma responde. */}
      <Section title="Camadas" note="Cada uma responde uma pergunta diferente.">
        <Grid min={250}>
          {CAMADAS.map((c) => (
            <Link key={c.to} to={c.to} className="camada-card">
              <span className="camada-card__titulo">{c.titulo}</span>
              <span className="t-small">{c.pergunta}</span>
            </Link>
          ))}
        </Grid>
      </Section>

      <QueryState isLoading={isLoading} isError={isError}>
        {['seasonal', 'subseasonal', 'synoptic'].map((horizon) => (
          <Section key={horizon} title={HORIZON_LABEL[horizon]}>
            <Grid min={220}>
              {(grouped[horizon] ?? []).length === 0 ? (
                <Empty>Nenhum perigo catalogado neste horizonte.</Empty>
              ) : (
                grouped[horizon]!.map((h) => <HazardCard key={h.id} hazard={h} />)
              )}
            </Grid>
          </Section>
        ))}
      </QueryState>

      {/* Teleconexao DEPOIS: e a explicacao do mecanismo, e explicacao vem
          depois do fato para quem chegou perguntando "onde". */}
      <Section
        title="De onde vem o sinal — Pacifico equatorial → RS"
        note={
          <>
            Este mapa para no contorno do estado: o sinal sazonal e estadual e nao tem resolucao
            municipal. O detalhamento por municipio esta em <Link to="/municipios">Municipios</Link>.
          </>
        }
      >
        <Panel pad="tight">
          <MapaTeleconexao />
        </Panel>
      </Section>

      {/* O enquadramento honesto, no fim e por extenso. Nao e rodape: e a
          fronteira que define o que tudo acima significa. */}
      <Section title="O que esta central NAO faz">
        <Panel tone="verdict">
          <ul className="lista-marcas" data-tom="alerta">
            <li>
              <strong>Nao preve cheia.</strong> Nenhuma camada antecipa evento individual. Maio de
              2024 foi bloqueio sinotico, e nenhuma versao desta engine o teria previsto (ADR-013).
            </li>
            <li>
              <strong>Nao ha previsao aceita.</strong> Nenhum modelo passou o criterio da ADR-007 —
              a climatologia segue vigente. A previsao prospectiva na tela e do CPC/NOAA.
            </li>
            <li>
              <strong>Nao ha previsao para 2027.</strong> O horizonte util de ENSO e de ~9 meses.
              Para 2027 o instrumento e o risco estrutural, que nao depende de previsao.
            </li>
            <li>
              <strong>Sem resolucao de bairro.</strong> O poligono municipal inteiro recebe um
              valor. Nao existe ponto de enchente por rua nesta base.
            </li>
          </ul>
        </Panel>
      </Section>
    </View>
  );
}

function Numero({
  n,
  label,
  para,
  tom,
}: {
  n: number | undefined;
  label: string;
  para: string;
  tom?: 'alerta' | 'acento';
}) {
  return (
    <Link to={para} className="numero-card" data-tom={tom}>
      {n === undefined ? (
        <span className="skeleton" style={{ height: 34, width: '4ch', display: 'block' }} />
      ) : (
        <span className="numero-card__n t-hero">{n.toLocaleString('pt-BR')}</span>
      )}
      <span className="t-small">{label}</span>
    </Link>
  );
}
