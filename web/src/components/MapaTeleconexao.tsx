import { useAppState, useRiskCurrent } from '../api/hooks';
import { ProvenanceBadge } from './ProvenanceBadge';
import { BRUMA, BRUMA_FRACA, GRID, LINHA, NIVEL, NIVEL_LABEL, alpha, divergingValue } from '../theme/palette';
import './MapaTeleconexao.css';

/**
 * Mapa de teleconexao — a unica geografia que esta engine pode desenhar
 * honestamente hoje.
 *
 * Por que ESTE mapa e nao um coropletico do RS por municipio: nao existe
 * nenhuma serie municipal na base. Inventar celulas regionais para colorir
 * seria numero sem proveniencia, que o §0 do contrato chama de bug. O que
 * existe e um par de fatos geograficos reais:
 *
 *   1. a caixa Nino 3.4 (5N-5S, 170E-120W), colorida pelo ONI corrente —
 *      indice MEDIDO, escala divergente do dado (FRIO/QUENTE);
 *   2. o RS como alvo, colorido pelo nivel do perigo sazonal — MODELADO,
 *      via heuristica sobre o ONI (ADR-007 nao passou por nenhum modelo).
 *
 * Os dois selos aparecem separados de proposito: o mapa mostra uma cadeia
 * causal cuja origem e medida e cujo destino e inferido, e essa assimetria
 * e o conteudo, nao um detalhe.
 *
 * Projecao: equirretangular simples, 6 px por grau, janela lon [-180,-30] x
 * lat [-60,25]. Suficiente para leitura de posicao relativa; nao e carta
 * nautica e nao pretende ser.
 */

const LON0 = -180;
const LAT0 = 25;
const PPD = 6; // px por grau
const W = 150 * PPD; // 900
const H = 85 * PPD; // 510

const px = (lon: number) => (lon - LON0) * PPD;
const py = (lat: number) => (LAT0 - lat) * PPD;

const path = (pts: [number, number][], close = true) =>
  pts.map(([lo, la], i) => `${i === 0 ? 'M' : 'L'}${px(lo).toFixed(1)},${py(la).toFixed(1)}`).join(' ') +
  (close ? ' Z' : '');

/** Contorno da America do Sul, generalizado (~30 vertices). */
const AMERICA_SUL: [number, number][] = [
  [-81, -4], [-79, -8], [-76, -14], [-70, -18], [-70, -23], [-71, -30],
  [-73, -37], [-74, -44], [-75, -50], [-70, -55], [-66, -55], [-65, -50],
  [-62, -42], [-57, -38], [-57, -34], [-53, -34], [-48, -28], [-48, -25],
  [-44, -23], [-39, -18], [-37, -11], [-35, -6], [-40, -2], [-45, -1],
  [-50, 0], [-52, 4], [-60, 8], [-64, 10], [-72, 12], [-77, 8], [-79, 2],
];

/** Rio Grande do Sul, generalizado. */
const RS: [number, number][] = [
  // fronteira norte (divisa com SC), oeste -> leste
  [-54.5, -27.4], [-53.5, -27.15], [-51.5, -27.2], [-49.9, -28.6],
  // litoral, Torres -> Chui
  [-49.7, -29.35], [-50.9, -31.4], [-52.1, -32.4], [-52.6, -33.2], [-53.4, -33.75],
  // fronteira sul/oeste com o Uruguai (Lagoa Mirim -> Quarai)
  [-53.5, -33.0], [-54.5, -31.6], [-55.6, -30.9], [-56.9, -30.1], [-57.6, -30.2],
  // rio Uruguai, sudoeste -> nordeste
  [-56.3, -29.0], [-55.6, -28.1],
];

/* --- Inset do RS: mesma geometria, 22 px/grau (≈3,7x o mapa principal) --- */
const IPPD = 22;
const RS_LON0 = -57.6;
const RS_LAT0 = -27.1;
const INSET = {
  x: 40,
  y: 262,
  pad: 18,
  w: 7.9 * IPPD + 36,
  h: 6.65 * IPPD + 78,
};

const insetPath = (pts: [number, number][]) =>
  pts
    .map(
      ([lo, la], i) =>
        `${i === 0 ? 'M' : 'L'}${((lo - RS_LON0) * IPPD).toFixed(1)},${((RS_LAT0 - la) * IPPD).toFixed(1)}`,
    )
    .join(' ') + ' Z';

/** Caixa em graus -> retangulo SVG. */
const box = (lonW: number, lonE: number, latN: number, latS: number) => ({
  x: px(lonW),
  y: py(latN),
  width: px(lonE) - px(lonW),
  height: py(latS) - py(latN),
});

export function MapaTeleconexao() {
  const state = useAppState();
  const risk = useRiskCurrent();

  const oni = state.data?.headline.oni ?? null;
  const classificacao = state.data?.headline.classification ?? null;

  // O perigo sazonal e o unico com alcance geografico declarado no catalogo.
  const sazonal = risk.data?.hazards.find((h) => h.horizon === 'seasonal' && h.level !== null) ?? null;
  const nivel = (sazonal?.level ?? null) as keyof typeof NIVEL | null;

  // ONI -> cor divergente; dominio ±3 °C cobre os extremos historicos.
  const corNino = oni === null ? BRUMA : divergingValue(oni, 3);
  const corRS = nivel ? NIVEL[nivel] : GRID;

  // Nino 3.4: 5N-5S, 170E-120W (170E cai fora da janela; recortado em -180).
  const n34 = box(-180, -120, 5, -5);
  // Nino 1+2: 0-10S, 90W-80W. Contexto geografico, sem serie na base.
  const n12 = box(-90, -80, 0, -10);

  return (
    <figure className="mapa">
      <svg
        className="mapa__svg"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={
          oni === null
            ? 'Mapa de teleconexao: ONI indisponivel'
            : `Mapa de teleconexao: ONI ${oni.toFixed(2)} na caixa Nino 3.4 do Pacifico equatorial, ` +
              `perigo sazonal ${nivel ? NIVEL_LABEL[nivel] : 'indisponivel'} no Rio Grande do Sul`
        }
      >
        <defs>
          <pattern id="mapa-grade" width={30 * PPD} height={15 * PPD} patternUnits="userSpaceOnUse">
            <path d={`M${30 * PPD} 0 L0 0 0 ${15 * PPD}`} fill="none" stroke={LINHA} strokeWidth="1" />
          </pattern>
          <marker id="mapa-seta" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M0,0 L10,5 L0,10 Z" fill={BRUMA} />
          </marker>
        </defs>

        {/* oceano + grade de 15/30 graus: escala legivel sem eixo explicito */}
        <rect width={W} height={H} fill="#101A1F" />
        <rect width={W} height={H} fill="url(#mapa-grade)" />

        {/* equador */}
        <line x1="0" y1={py(0)} x2={W} y2={py(0)} stroke={BRUMA_FRACA} strokeWidth="1" strokeDasharray="6 6" />
        <text x={px(-118)} y={py(0) - 8} className="mapa__tick">equador</text>

        {/* caixa Nino 3.4 — colorida pelo ONI (dado MEDIDO, escala divergente) */}
        <rect {...n34} fill={oni === null ? 'none' : alpha(corNino, 0.55)} stroke={corNino} strokeWidth="2" />
        <text x={n34.x + 14} y={n34.y - 10} className="mapa__rotulo">NIÑO 3.4</text>
        <text x={n34.x + 14} y={n34.y + n34.height + 22} className="mapa__valor">
          ONI {oni === null ? '—' : oni.toFixed(2)}
          {classificacao ? `  ${classificacao}` : ''}
        </text>

        {/* caixa Nino 1+2 — contexto, sem serie na base: contorno tracejado, sem preenchimento */}
        <rect {...n12} fill="none" stroke={BRUMA_FRACA} strokeWidth="1" strokeDasharray="4 4" />
        <text x={n12.x - 4} y={n12.y - 8} className="mapa__tick">NIÑO 1+2 (sem serie)</text>

        {/* continente */}
        <path d={path(AMERICA_SUL)} fill="#16211F" stroke={LINHA} strokeWidth="1.5" />

        {/* arco de teleconexao: origem medida -> alvo inferido. Tracejado
            porque o vinculo e estatistico, nao um transporte fisico desenhado. */}
        <path
          d={`M${n34.x + n34.width} ${n34.y + n34.height / 2} Q ${px(-95)} ${py(-38)} ${px(-53.5)} ${py(-30.4)}`}
          fill="none"
          stroke={BRUMA}
          strokeWidth="1.5"
          strokeDasharray="7 7"
          markerEnd="url(#mapa-seta)"
        />

        {/* RS — colorido pelo NIVEL do perigo sazonal (MODELADO) */}
        <path d={path(RS)} fill={alpha(corRS, 0.75)} stroke={corRS} strokeWidth="2" />
        <circle cx={px(-53.5)} cy={py(-30.4)} r="34" fill="none" stroke={corRS} strokeWidth="1" opacity="0.45" />
        {/* linha de chamada para o inset */}
        <line
          x1={px(-53.5) + 30}
          y1={py(-30.4) + 16}
          x2={INSET.x}
          y2={INSET.y + 24}
          stroke={LINHA}
          strokeWidth="1"
        />

        {/* Inset do RS a 4x — sem ele o alvo fica com ~50px e nao se le.
            Preenchimento CHAPADO de proposito: nao ha variacao sub-estadual
            na base, e um gradiente interno sugeriria uma que nao existe. */}
        <g transform={`translate(${INSET.x} ${INSET.y})`}>
          <rect
            width={INSET.w}
            height={INSET.h}
            rx="8"
            fill="#101A1F"
            stroke={LINHA}
            strokeWidth="1"
          />
          <path
            d={insetPath(RS)}
            transform={`translate(${INSET.pad} ${INSET.pad})`}
            fill={alpha(corRS, 0.75)}
            stroke={corRS}
            strokeWidth="2.5"
          />
          <text x={INSET.pad} y={INSET.h - 34} className="mapa__rotulo">RIO GRANDE DO SUL</text>
          <text x={INSET.pad} y={INSET.h - 12} className="mapa__valor">
            perigo sazonal: {nivel ? NIVEL_LABEL[nivel] : '—'}
          </text>
        </g>
      </svg>

      <figcaption className="mapa__legenda">
        <span className="mapa__chave">
          <span className="mapa__amostra" style={{ background: corNino }} />
          Niño 3.4 — anomalia ONI <ProvenanceBadge basis="measured" />
        </span>
        <span className="mapa__chave">
          <span className="mapa__amostra" style={{ background: corRS }} />
          RS — nivel do perigo sazonal <ProvenanceBadge basis={sazonal?.basis ?? null} />
        </span>
        <span className="t-note mapa__nota">
          Geometria generalizada, projecao equirretangular. O arco marca vinculo
          estatistico ENSO→RS, nao trajetoria fisica. Nenhuma variacao dentro do
          RS e representada: nao existe serie sub-estadual na base.
        </span>
      </figcaption>
    </figure>
  );
}
