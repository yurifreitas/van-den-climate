import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { MalhaResponse, MunicipioRisco } from '../api/types';
import { ABISSAL, BRUMA_FRACA, GIZ, GRID, LINHA, NIVEL, alpha, sequencial } from '../theme/palette';
import './MapaMunicipal.css';

/**
 * Coropletico dos 497 municipios do RS.
 *
 * Por que SVG desenhado a mao e nao uma biblioteca de mapa (Leaflet/MapLibre):
 * nao ha camada de tiles aqui e nem deve haver. Tile de rua convida a leitura
 * "isto e um mapa de onde vai alagar na minha quadra", e a base nao tem
 * resolucao intramunicipal nenhuma — o poligono inteiro recebe UM valor. Um
 * mapa sem fundo de rua comunica o grao correto pela propria austeridade, e
 * ainda evita 400 KB de runtime para desenhar 497 poligonos estaticos.
 *
 * Projecao: equirretangular com correcao de cosseno da latitude media. Em
 * ~30°S isso encurta a longitude em ~13%; sem a correcao o RS aparece
 * horizontalmente esticado e qualquer gaucho percebe que o mapa esta errado
 * antes de olhar o dado.
 */

const W = 1000;
const H = 760;
const PAD = 12;

/**
 * `recursos` e `aguas` compartilham o preenchimento transparente e diferem na
 * BORDA: na camada de agua a malha e ruido de fundo (a informacao esta no
 * raster), na de recursos ela e a unica referencia geografica que resta —
 * sem borda cheia, 1.600 pontos flutuam sobre o nada.
 */
type Camada = 'risco' | 'impacto' | 'deficit' | 'exposicao' | 'aguas' | 'recursos';

/**
 * Teto de pontos desenhados no mapa.
 *
 * 6.000 circulos ficam em torno de 6 mil nos de SVG, que o navegador reconcilia
 * sem engasgo mesmo em maquina modesta. Acima disso o mapa do estado inteiro ja
 * virou mancha continua — nao ha densidade a mais para ler, so custo a mais
 * para pagar. Quem chama recebe quantos pontos foram desenhados e DIZ isso na
 * tela: descarte silencioso lê-se como cobertura completa.
 */
export const TETO_PONTOS = 6000;

/** Quantos pontos o mapa desenharia para um conjunto — para a legenda declarar. */
export function pontosDesenhados(total: number): number {
  const passo = Math.ceil(total / TETO_PONTOS);
  return passo > 1 ? Math.ceil(total / passo) : total;
}

export const CAMADAS: { id: Camada; label: string; hint: string }[] = [
  { id: 'risco', label: 'Risco integrado', hint: 'I+D+E modulados pelo estado sazonal' },
  { id: 'impacto', label: 'Impacto 2024', hint: 'perigos hidricos e danos observados' },
  { id: 'deficit', label: 'Deficit de prevencao', hint: 'plano, execucao e alcance do alerta' },
  { id: 'exposicao', label: 'Exposicao', hint: 'populacao e grupos em maior risco' },
  {
    id: 'aguas',
    label: 'Agua — rios e memoria',
    hint: 'JRC 1984-2021: agua permanente, sazonal, perdida e efemera',
  },
];

/** Achata Polygon/MultiPolygon num array de aneis externos. */
function aneis(geometry: MalhaFeatureGeometry): number[][][] {
  if (geometry.type === 'Polygon') return geometry.coordinates as number[][][];
  return (geometry.coordinates as number[][][][]).flatMap((poly) => poly);
}

type MalhaFeatureGeometry = MalhaResponse['features'][number]['geometry'];

function bbox(features: MalhaResponse['features']) {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const f of features) {
    for (const ring of aneis(f.geometry)) {
      for (const [x, y] of ring) {
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
    }
  }
  return { minX, minY, maxX, maxY };
}

/** Valor da camada para um municipio; null significa "sem base", nunca 0. */
function valorDaCamada(m: MunicipioRisco, camada: Camada): number | null {
  switch (camada) {
    case 'risco':
      return m.score === null ? null : m.score / 100;
    case 'impacto':
      return m.componentes.impacto.valor;
    case 'deficit':
      return m.componentes.deficit_prevencao.valor;
    case 'exposicao':
      return m.componentes.exposicao.valor;
    case 'aguas':
      // A informacao desta camada esta no raster, nao no poligono. O valor
      // serve so para o tooltip: fracao do municipio com precedente de agua.
      return m.aguas?.memoria_hidrica_frac ?? null;
    case 'recursos':
      // A informacao esta nos pontos. O tooltip mostra o indice, que e o que
      // torna um vazio de cobertura relevante ou irrelevante.
      return m.score === null ? null : m.score / 100;
  }
}

/**
 * Cor da celula. Duas gramaticas distintas de proposito:
 *   - `risco` usa a escala ORDINAL de nivel (NIVEL), porque o que importa e a
 *     faixa de acao, e a faixa tem corte declarado no model_card;
 *   - as demais usam a escala SEQUENCIAL de um matiz, porque sao magnitudes
 *     continuas sem corte semantico. Usar a escala de nivel nelas inventaria
 *     limiares que o modelo nao declara.
 * Sem dado -> hachura, nunca um cinza que se confunda com "valor baixo".
 */
function cor(m: MunicipioRisco, camada: Camada): string | null {
  // Na camada de agua o poligono NAO e preenchido: quem carrega a informacao
  // e o raster embaixo. Preencher aqui cobriria exatamente o que se quer ver.
  if (camada === 'aguas' || camada === 'recursos') return 'none';
  const v = valorDaCamada(m, camada);
  if (v === null) return null;
  if (camada === 'risco') return m.level ? NIVEL[m.level] : null;
  const matiz = camada === 'deficit' ? NIVEL.elevated : camada === 'impacto' ? NIVEL.high : NIVEL.low;
  return sequencial(v, matiz);
}

export function MapaMunicipal({
  malha,
  municipios,
  camada,
  selecionado,
  onSelecionar,
  aguas,
  recursos,
  coresRecurso,
}: {
  malha: MalhaResponse;
  municipios: MunicipioRisco[];
  camada: Camada;
  selecionado: number | null;
  onSelecionar: (cod: number | null) => void;
  /** Overlay de memoria hidrica. `null` esconde a camada. */
  aguas?: { url: string; bbox: { lon_min: number; lon_max: number; lat_min: number; lat_max: number } } | null;
  /** Pontos de recurso (hospital, bombeiro, CAPS...). `null` esconde. */
  recursos?: { lon: number; lat: number; papel: string; nome: string | null }[] | null;
  /** Cor por papel, vinda de quem chama — o mapa nao inventa vocabulario. */
  coresRecurso?: Record<string, string>;
}) {
  const [hover, setHover] = useState<{ m: MunicipioRisco; x: number; y: number } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const porCodigo = useMemo(() => {
    const map = new Map<number, MunicipioRisco>();
    for (const m of municipios) map.set(m.cod_mun, m);
    return map;
  }, [municipios]);

  // Projecao e paths sao caros (497 poligonos) e dependem SO da malha —
  // recalcular a cada troca de camada ou hover derrubaria o frame rate.
  const projetado = useMemo(() => {
    const { minX, minY, maxX, maxY } = bbox(malha.features);
    const latMedia = ((minY + maxY) / 2) * (Math.PI / 180);
    const kx = Math.cos(latMedia);
    const larguraGeo = (maxX - minX) * kx;
    const alturaGeo = maxY - minY;
    const escala = Math.min((W - 2 * PAD) / larguraGeo, (H - 2 * PAD) / alturaGeo);
    const offX = (W - larguraGeo * escala) / 2;
    const offY = (H - alturaGeo * escala) / 2;

    const px = (lon: number) => offX + (lon - minX) * kx * escala;
    const py = (lat: number) => offY + (maxY - lat) * escala;

    const feats = malha.features.map((f) => {
      const d = aneis(f.geometry)
        .map(
          (ring) =>
            ring
              .map(([lo, la], i) => `${i === 0 ? 'M' : 'L'}${px(lo).toFixed(1)},${py(la).toFixed(1)}`)
              .join(' ') + ' Z',
        )
        .join(' ');
      return { cod: Number(f.properties.codarea), d };
    });
    // A projecao e linear em lon/lat, entao o overlay do JRC (que e uma grade
    // equirretangular) se posiciona com quatro numeros — sem reprojetar nada.
    return { paths: feats, px, py };
  }, [malha]);

  const { paths, px, py } = projetado;
  const caixaAguas = aguas
    ? {
        x: px(aguas.bbox.lon_min),
        y: py(aguas.bbox.lat_max),
        width: px(aguas.bbox.lon_max) - px(aguas.bbox.lon_min),
        height: py(aguas.bbox.lat_min) - py(aguas.bbox.lat_max),
      }
    : null;

  /**
   * Retangulo do SVG, em cache.
   *
   * ESTA e a causa real do travamento, e o teto de pontos so tinha adiado o
   * sintoma. `getBoundingClientRect()` num elemento SVG forca o navegador a
   * recalcular o layout da arvore inteira — e estava sendo chamado a CADA
   * `mousemove`, sessenta vezes por segundo, sobre um SVG de milhares de nos.
   * Nao e custo de React: e thrash de layout, e por isso escala com o numero
   * de nos desenhados e nao com o trabalho de reconciliacao.
   *
   * O retangulo so muda quando a janela ou o container mudam de tamanho, entao
   * e medido uma vez por entrada do ponteiro e no `resize`.
   */
  const rectRef = useRef<DOMRect | null>(null);
  const medir = useCallback(() => {
    rectRef.current = svgRef.current?.getBoundingClientRect() ?? null;
  }, []);

  useEffect(() => {
    medir();
    window.addEventListener('resize', medir);
    return () => window.removeEventListener('resize', medir);
  }, [medir]);

  // O tooltip acompanha o ponteiro, mas nao precisa de um estado por evento:
  // um quadro por frame basta para o olho e corta as atualizacoes redundantes
  // que o navegador emite entre dois frames.
  const pendente = useRef<number | null>(null);
  const mover = useCallback((e: React.MouseEvent, m: MunicipioRisco) => {
    const rect = rectRef.current;
    if (!rect) return;
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    if (pendente.current !== null) return;
    pendente.current = requestAnimationFrame(() => {
      pendente.current = null;
      setHover({ m, x, y });
    });
  }, []);

  /**
   * Camada de pontos, MEMOIZADA e com teto declarado.
   *
   * Isto aqui matou a tela de recursos em producao, e o mecanismo merece ficar
   * escrito porque ele nao aparece em teste de unidade nenhum.
   *
   * Cada ponto rendia dois nos de DOM (um `<circle>` e um `<title>` filho). Com
   * a familia de socorro sozinha eram ~3,2 mil nos e ninguem notava. Ligando
   * abrigo, suprimento e infraestrutura, os 18,7 mil pontos viravam ~37 mil nos
   * — e como `hover` e estado DESTE componente, cada movimento do mouse sobre
   * um municipio re-renderizava a arvore inteira. Passar o mouse pelo mapa
   * algumas vezes derrubava o renderizador: a aba ficava em branco.
   *
   * Tres correcoes, nesta ordem de importancia:
   *
   *   1. a camada de pontos sai do caminho do `hover` (este `useMemo`), entao
   *      mover o mouse reconcilia so o tooltip;
   *   2. o `<title>` por ponto sai — era metade dos nos, e o tooltip nativo em
   *      cima de um circulo de 3 px nunca foi a forma de ler este mapa;
   *   3. teto de pontos desenhados, com o descarte DECLARADO em vez de
   *      silencioso. Acima do teto o mapa vira mancha e para de informar
   *      densidade de qualquer jeito — o que se perde ao amostrar e menos que
   *      o que se perde travando.
   */
  /**
   * Camada de municipios, tambem fora do caminho do `hover`.
   *
   * Sao 497 `<path>`, cada um com um `<title>` — mil nos que o React
   * reconciliava a cada movimento do ponteiro sem que nenhum deles pudesse ter
   * mudado, porque `hover` so alimenta o tooltip.
   */
  const camadaMunicipios = useMemo(
    () => (
      <>
        {paths.map(({ cod, d }) => {
          const m = porCodigo.get(cod);
          const c = m ? cor(m, camada) : null;
          const ativo = selecionado === cod;
          return (
            <path
              key={cod}
              d={d}
              className={`mapa-mun__mun${ativo ? ' mapa-mun__mun--ativo' : ''}`}
              fill={c === null ? 'url(#sem-dado)' : c === 'none' ? 'transparent' : alpha(c, 0.88)}
              stroke={ativo ? '#FFFFFF' : LINHA}
              strokeWidth={ativo ? 2 : 0.5}
              // Na camada de agua a malha municipal e referencia, nao dado:
              // 497 bordas em opacidade cheia formam uma trama que compete com
              // os rios e vence, porque e mais regular.
              strokeOpacity={camada === 'aguas' && !ativo ? 0.35 : 1}
              onMouseMove={(e) => m && mover(e, m)}
              onClick={() => onSelecionar(ativo ? null : cod)}
              tabIndex={-1}
            >
              <title>{m ? m.municipio : cod}</title>
            </path>
          );
        })}
      </>
    ),
    [paths, porCodigo, camada, selecionado, mover, onSelecionar],
  );

  const camadaPontos = useMemo(() => {
    if (!recursos?.length) return null;
    // Amostragem deterministica (passo fixo, nao aleatoria): o mesmo conjunto
    // de filtros desenha sempre os mesmos pontos, e o mapa nao "pisca" entre
    // renders.
    const passo = Math.ceil(recursos.length / TETO_PONTOS);
    const visiveis = passo > 1 ? recursos.filter((_, i) => i % passo === 0) : recursos;
    return (
      <g style={{ pointerEvents: 'none' }}>
        {visiveis.map((p, i) => (
          <circle
            key={`${p.papel}-${i}`}
            cx={px(p.lon)}
            cy={py(p.lat)}
            r={3}
            fill={coresRecurso?.[p.papel] ?? GIZ}
            stroke={ABISSAL}
            strokeWidth={0.8}
          />
        ))}
      </g>
    );
  }, [recursos, coresRecurso, px, py]);

  return (
    <div className="mapa-mun">
      <svg
        ref={svgRef}
        className="mapa-mun__svg"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Mapa do Rio Grande do Sul por municipio — camada ${camada}`}
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          {/* Hachura para "sem base de avaliacao". Um cinza chapado seria lido
              como "risco baixo"; hachura nao se confunde com valor. */}
          <pattern id="sem-dado" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="7" height="7" fill={GRID} />
            <line x1="0" y1="0" x2="0" y2="7" stroke={BRUMA_FRACA} strokeWidth="1.4" />
          </pattern>
        </defs>

        {/* Overlay de memoria hidrica ENTRE o fundo e os poligonos: precisa
            ficar sob as bordas municipais (que dao a referencia geografica)
            e sob o hit-area do clique, senao a imagem rouba o ponteiro. */}
        {caixaAguas && (
          <image
            href={aguas!.url}
            {...caixaAguas}
            preserveAspectRatio="none"
            style={{ imageRendering: 'pixelated', pointerEvents: 'none' }}
          />
        )}

        {camadaMunicipios}

        {camadaPontos}
      </svg>

      {hover && (
        <div
          className="mapa-mun__tooltip"
          style={{
            left: `${(hover.x / W) * 100}%`,
            top: `${(hover.y / H) * 100}%`,
          }}
          role="presentation"
        >
          <strong>{hover.m.municipio}</strong>
          <span className="mapa-mun__tooltip-linha">
            <span>{CAMADAS.find((c) => c.id === camada)!.label}</span>
            <span className="num">
              {(() => {
                const v = valorDaCamada(hover.m, camada);
                if (v === null) return '—';
                if (camada === 'risco') return (v * 100).toFixed(1);
                if (camada === 'aguas') return `${(v * 100).toFixed(1)}%`;
                return v.toFixed(2);
              })()}
            </span>
          </span>
          <span className="mapa-mun__tooltip-nota">
            {hover.m.completude === 'insuficiente'
              ? 'sem base suficiente para avaliar'
              : `pop. ${hover.m.populacao?.toLocaleString('pt-BR') ?? '—'}`}
          </span>
        </div>
      )}
    </div>
  );
}

export type { Camada };
