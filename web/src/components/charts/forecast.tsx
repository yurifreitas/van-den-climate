import { useMemo } from 'react';
import type { EChartsOption } from 'echarts';
import { EChart, GRID_BASE, reducedMotion } from './EChart';
import type { AnalogYear, AttributionBlock, TercileSet } from '../../api/types';
import {
  BRUMA,
  BRUMA_FRACA,
  CARTA,
  FRIO,
  GIZ,
  GRID,
  QUENTE,
  alpha,
  categorico,
  sequencial,
} from '../../theme/palette';

const TERCIL = ['Abaixo', 'Normal', 'Acima'];
const TERCIL_COR = [FRIO, BRUMA_FRACA, QUENTE];

/**
 * Previsao x climatologia por tercil, com barra de erro.
 *
 * O que a tela precisa responder nao e "qual a probabilidade" — e "o quanto
 * isso DESLOCA em relacao ao acaso". Por isso a climatologia aparece como
 * marca fantasma atras, e o deslocamento em pontos percentuais e o rotulo
 * direto. Sem a referencia, 38% parece alto quando o acaso ja da 33%.
 */
export function TercileShiftChart({
  forecast,
  climatology,
  se,
  height = 220,
}: {
  forecast: TercileSet;
  climatology: TercileSet;
  se?: number;
  height?: number;
}) {
  const option = useMemo<EChartsOption>(() => {
    const f = [forecast.below, forecast.normal, forecast.above];
    const c = [climatology.below, climatology.normal, climatology.above];
    const err = se ?? 0;

    return {
      animation: !reducedMotion,
      grid: { ...GRID_BASE, left: 56 },
      tooltip: {
        trigger: 'axis',
        formatter: (params: unknown) => {
          const arr = params as { dataIndex: number }[];
          const i = arr[0].dataIndex;
          const d = ((f[i] - c[i]) * 100).toFixed(1);
          return [
            `<b>${TERCIL[i]}</b>`,
            `previsto ${(f[i] * 100).toFixed(1)}%`,
            `climatologia ${(c[i] * 100).toFixed(1)}%`,
            `deslocamento ${Number(d) > 0 ? '+' : ''}${d} p.p.`,
            err ? `erro padrao ±${(err * 100).toFixed(1)} p.p.` : '',
          ]
            .filter(Boolean)
            .join('<br/>');
        },
      },
      xAxis: { type: 'category', data: TERCIL },
      yAxis: {
        type: 'value',
        max: Math.max(0.6, ...f, ...c),
        axisLabel: { formatter: (v: number) => `${Math.round(v * 100)}%` },
      },
      series: [
        {
          // fantasma da climatologia: contorno, sem preenchimento solido
          type: 'bar',
          name: 'climatologia',
          data: c,
          barGap: '-100%',
          barWidth: 24,
          itemStyle: { color: 'transparent', borderColor: BRUMA_FRACA, borderWidth: 1, borderType: 'solid' },
          silent: true,
          z: 1,
        },
        {
          type: 'bar',
          name: 'previsto',
          data: f.map((v, i) => ({
            value: v,
            // ponta arredondada no topo, quadrada na base (DESIGN.md §5)
            itemStyle: { color: alpha(TERCIL_COR[i], 0.85), borderRadius: [4, 4, 0, 0] },
          })),
          barWidth: 24,
          z: 2,
          label: {
            show: true,
            position: 'top',
            color: GIZ,
            fontSize: 11,
            formatter: (p: { dataIndex: number; value: number }) => {
              const d = (p.value - c[p.dataIndex]) * 100;
              return `${Math.abs(d) < 0.05 ? '=' : d > 0 ? '+' : ''}${d.toFixed(0)}`;
            },
          },
        },
        err
          ? {
              // barra de erro: incerteza nunca fica implicita
              type: 'custom',
              name: 'erro padrao',
              // `_params` nao e usado: o desenho sai todo de `api`. Mantido na
              // assinatura porque o ECharts passa os dois posicionalmente.
              renderItem: (_params: unknown, api: { value: (i: number) => number; coord: (v: number[]) => number[]; size?: (v: number[]) => number[] }) => {
                const idx = api.value(0);
                const v = api.value(1);
                const hi = api.coord([idx, v + err]);
                const lo = api.coord([idx, Math.max(0, v - err)]);
                const w = 7;
                return {
                  type: 'group',
                  children: [
                    { type: 'line', shape: { x1: hi[0], y1: hi[1], x2: lo[0], y2: lo[1] }, style: { stroke: GIZ, lineWidth: 1 } },
                    { type: 'line', shape: { x1: hi[0] - w, y1: hi[1], x2: hi[0] + w, y2: hi[1] }, style: { stroke: GIZ, lineWidth: 1 } },
                    { type: 'line', shape: { x1: lo[0] - w, y1: lo[1], x2: lo[0] + w, y2: lo[1] }, style: { stroke: GIZ, lineWidth: 1 } },
                  ],
                };
              },
              data: f.map((v, i) => [i, v]),
              z: 3,
            }
          : undefined,
      ].filter(Boolean) as EChartsOption['series'],
      legend: { bottom: 0, data: ['previsto', 'climatologia'] },
    };
  }, [forecast, climatology, se, height]);

  return (
    <EChart
      option={option}
      height={height}
      ariaLabel={`Probabilidade por tercil contra climatologia: abaixo ${(forecast.below * 100).toFixed(0)}%, normal ${(forecast.normal * 100).toFixed(0)}%, acima ${(forecast.above * 100).toFixed(0)}%`}
    />
  );
}

/**
 * Sankey da atribuicao: quanto de cada bloco causal sobrevive a remocao do
 * ENSO. Fluxo, e nao barra, porque a pergunta e de REDISTRIBUICAO — para onde
 * a explicacao migra quando o driver dominante sai.
 */
export function AttributionSankey({
  blocks,
  height = 300,
}: {
  blocks: AttributionBlock[];
  height?: number;
}) {
  const option = useMemo<EChartsOption>(() => {
    const nodes = [
      { name: 'variancia explicada', itemStyle: { color: BRUMA } },
      ...blocks.map((b, i) => ({ name: b.label, itemStyle: { color: categorico(i) } })),
      { name: 'sem ENSO', itemStyle: { color: BRUMA_FRACA } },
    ];
    const links = [
      ...blocks.map((b, i) => ({
        source: 'variancia explicada',
        target: b.label,
        value: Math.max(b.share_full, 0.001),
        lineStyle: { color: alpha(categorico(i), 0.3) },
      })),
      ...blocks.map((b, i) => ({
        source: b.label,
        target: 'sem ENSO',
        value: Math.max(b.share_without_enso, 0.001),
        lineStyle: { color: alpha(categorico(i), 0.18) },
      })),
    ];
    return {
      animation: !reducedMotion,
      tooltip: {
        trigger: 'item',
        formatter: (p: unknown) => {
          const q = p as { dataType: string; name: string; value: number };
          return q.dataType === 'edge'
            ? `${q.name}<br/>share ${(q.value * 100).toFixed(1)}%`
            : q.name;
        },
      },
      series: [
        {
          type: 'sankey',
          data: nodes,
          links,
          emphasis: { focus: 'adjacency' },
          label: { color: GIZ, fontSize: 10 },
          lineStyle: { curveness: 0.5 },
          nodeWidth: 10,
          nodeGap: 10,
          left: 8,
          right: 96,
        },
      ],
    };
  }, [blocks]);
  return <EChart option={option} height={height} ariaLabel="Fluxo de variancia explicada por bloco causal, com e sem ENSO" />;
}

/**
 * Barras pareadas full vs sem-ENSO — a leitura exata que o sankey da de
 * forma qualitativa. As duas convivem: fluxo para a forma, barra para o valor.
 */
export function AttributionBars({ blocks, height = 220 }: { blocks: AttributionBlock[]; height?: number }) {
  const option = useMemo<EChartsOption>(
    () => ({
      animation: !reducedMotion,
      grid: { ...GRID_BASE, left: 8 },
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0 },
      xAxis: { type: 'value', axisLabel: { formatter: (v: number) => `${Math.round(v * 100)}%` } },
      yAxis: { type: 'category', data: blocks.map((b) => b.label), axisLabel: { color: BRUMA } },
      series: [
        {
          type: 'bar',
          name: 'completo',
          data: blocks.map((b, i) => ({ value: b.share_full, itemStyle: { color: categorico(i), borderRadius: [0, 4, 4, 0] } })),
          barWidth: 12,
        },
        {
          type: 'bar',
          name: 'sem ENSO',
          data: blocks.map((b, i) => ({
            value: b.share_without_enso,
            itemStyle: { color: alpha(categorico(i), 0.35), borderRadius: [0, 4, 4, 0] },
          })),
          barWidth: 12,
        },
      ],
    }),
    [blocks],
  );
  return <EChart option={option} height={height} ariaLabel="Share por bloco causal, completo contra sem ENSO" />;
}

/**
 * Anos analogos: dispersao similaridade x ano, tamanho por similaridade e
 * cor pelo tercil OBSERVADO naquele ano. Responde de uma vez "quais anos se
 * parecem" e "no que deu quando pareceu".
 */
export function AnalogScatter({ analogs, height = 240 }: { analogs: AnalogYear[]; height?: number }) {
  const option = useMemo<EChartsOption>(
    () => ({
      animation: !reducedMotion,
      grid: GRID_BASE,
      tooltip: {
        trigger: 'item',
        formatter: (p: unknown) => {
          const q = p as { data: number[] };
          const [year, sim, t] = q.data;
          return `<b>${year}</b><br/>similaridade ${sim.toFixed(2)}<br/>observado: ${TERCIL[t]}`;
        },
      },
      xAxis: { type: 'value', name: 'ano', min: 'dataMin', max: 'dataMax', axisLabel: { formatter: (v: number) => String(Math.round(v)) } },
      yAxis: { type: 'value', name: 'similaridade', min: 0, max: 1 },
      series: [
        {
          type: 'scatter',
          data: analogs.map((a) => [a.year, a.similarity, a.observed_tercile]),
          symbolSize: (d: number[]) => 8 + d[1] * 22,
          itemStyle: {
            // O ECharts tipa o callback com `CallbackDataParams`, cujo `data`
            // e `OptionDataItem` (pode ser undefined). Declarar `unknown` e
            // estreitar aqui e o mesmo padrao do `tooltip.formatter` acima.
            color: (p: unknown) => TERCIL_COR[(p as { data: number[] }).data[2]],
            // anel de 2px na cor da superficie separa marcas sobrepostas
            borderColor: CARTA,
            borderWidth: 2,
            opacity: 0.9,
          },
          markLine: {
            silent: true,
            symbol: 'none',
            lineStyle: { color: GRID },
            label: { color: BRUMA_FRACA, fontSize: 10, formatter: 'corte 0.5' },
            data: [{ yAxis: 0.5 }],
          },
        },
      ],
    }),
    [analogs],
  );
  return <EChart option={option} height={height} ariaLabel={`Dispersao de ${analogs.length} anos analogos por similaridade`} />;
}

/**
 * Distribuicao observada dos analogos por tercil — o "no que deu" agregado.
 * Se os anos parecidos deram Acima 6 de 8 vezes, isso e evidencia mesmo sem
 * nenhum modelo aceito.
 */
export function AnalogOutcomeBars({ analogs, height = 160 }: { analogs: AnalogYear[]; height?: number }) {
  const option = useMemo<EChartsOption>(() => {
    const counts = [0, 0, 0];
    analogs.forEach((a) => (counts[a.observed_tercile] += 1));
    const total = analogs.length || 1;
    return {
      animation: !reducedMotion,
      grid: { ...GRID_BASE, top: 12, bottom: 20 },
      tooltip: {
        trigger: 'item',
        formatter: (p: unknown) => {
          const q = p as { dataIndex: number; value: number };
          return `${TERCIL[q.dataIndex]}<br/>${q.value} de ${total} anos analogos<br/>${((q.value / total) * 100).toFixed(0)}%`;
        },
      },
      xAxis: { type: 'category', data: TERCIL },
      yAxis: { type: 'value', minInterval: 1, name: 'anos' },
      series: [
        {
          type: 'bar',
          data: counts.map((v, i) => ({
            value: v,
            itemStyle: { color: sequencial(v / Math.max(...counts, 1), TERCIL_COR[i]), borderRadius: [4, 4, 0, 0] },
          })),
          barWidth: 28,
          label: { show: true, position: 'top', color: GIZ, fontSize: 11 },
        },
      ],
    };
  }, [analogs]);
  return <EChart option={option} height={height} ariaLabel="Distribuicao do tercil observado nos anos analogos" />;
}
