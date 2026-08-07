import { useMemo, useRef, useState } from 'react';
import type { MalhaResponse, MunicipioRisco } from '../api/types';
import { BRUMA_FRACA, GRID, LINHA, NIVEL, alpha, sequencial } from '../theme/palette';
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

type Camada = 'risco' | 'impacto' | 'deficit' | 'exposicao' | 'aguas';

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
  if (camada === 'aguas') return 'none';
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
}: {
  malha: MalhaResponse;
  municipios: MunicipioRisco[];
  camada: Camada;
  selecionado: number | null;
  onSelecionar: (cod: number | null) => void;
  /** Overlay de memoria hidrica. `null` esconde a camada. */
  aguas?: { url: string; bbox: { lon_min: number; lon_max: number; lat_min: number; lat_max: number } } | null;
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

  const mover = (e: React.MouseEvent, m: MunicipioRisco) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    setHover({ m, x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

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
