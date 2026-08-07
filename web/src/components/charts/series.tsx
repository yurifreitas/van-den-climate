import { useMemo } from 'react';
import type { EChartsOption } from 'echarts';
import { EChart, GRID_BASE, reducedMotion } from './EChart';
import type { SeriesPoint, StateBlock } from '../../api/types';
import { BRUMA, FRIO, GIZ, GRID, QUENTE, alpha, diverging } from '../../theme/palette';

/**
 * Serie longa com banda divergente: area frio abaixo de zero, quente acima.
 *
 * Implementada como duas series empilhadas em zero com clip por eixo — e o
 * unico jeito de ter DUAS cores de preenchimento numa linha so sem inventar
 * um segundo eixo (DESIGN.md §5: um eixo, sempre).
 *
 * `phases` desenha markArea nos periodos de El Nino/La Nina — o contexto que
 * transforma a linha em narrativa, sem exigir que a pessoa conte picos.
 */
export function SeriesBandChart({
  points,
  height = 300,
  threshold = 0.5,
  label = 'indice',
}: {
  points: SeriesPoint[];
  height?: number;
  threshold?: number;
  label?: string;
}) {
  const option = useMemo<EChartsOption>(() => {
    const x = points.map((p) => p.timestamp.slice(0, 7));
    const v = points.map((p) => p.value);
    const pos = v.map((y) => (y > 0 ? y : 0));
    const neg = v.map((y) => (y < 0 ? y : 0));

    // faixas de evento: sequencias com |valor| acima do limiar operacional.
    // Tupla de DOIS elementos, nao array: `markArea.data` espera o par
    // [inicio, fim] (MarkArea2DDataItemOption), e um array solto passaria pelo
    // TypeScript so para o ECharts ignorar a faixa em silencio.
    type Faixa = [
      { xAxis: string; itemStyle: { color: string } },
      { xAxis: string; itemStyle: { color: string } },
    ];
    const phases: Faixa[] = [];
    let start: number | null = null;
    let sign = 0;
    v.forEach((y, i) => {
      const s = y >= threshold ? 1 : y <= -threshold ? -1 : 0;
      if (s !== sign) {
        if (start !== null && sign !== 0 && i - start >= 3) {
          phases.push([
            { xAxis: x[start], itemStyle: { color: alpha(sign > 0 ? QUENTE : FRIO, 0.07) } },
            { xAxis: x[i - 1], itemStyle: { color: alpha(sign > 0 ? QUENTE : FRIO, 0.07) } },
          ]);
        }
        start = i;
        sign = s;
      }
    });

    const last = points[points.length - 1];

    return {
      animation: !reducedMotion,
      grid: GRID_BASE,
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: x, boundaryGap: false, axisLabel: { interval: 'auto' } },
      yAxis: { type: 'value', name: label, nameTextStyle: { color: BRUMA, align: 'left' } },
      dataZoom: [
        // janela padrao de 20 anos nas series longas (DESIGN.md §5): na serie
        // completa a banda divergente some por densidade.
        { type: 'inside', start: Math.max(0, 100 - (240 / Math.max(points.length, 1)) * 100), end: 100 },
        { type: 'slider', height: 18, bottom: 0, borderColor: GRID, fillerColor: alpha(GIZ, 0.06), handleStyle: { color: BRUMA } },
      ],
      series: [
        {
          type: 'line',
          name: 'acima',
          data: pos,
          lineStyle: { width: 0 },
          areaStyle: { color: alpha(QUENTE, 0.32), origin: 'start' },
          symbol: 'none',
          stack: undefined,
          silent: true,
        },
        {
          type: 'line',
          name: 'abaixo',
          data: neg,
          lineStyle: { width: 0 },
          areaStyle: { color: alpha(FRIO, 0.32), origin: 'start' },
          symbol: 'none',
          silent: true,
        },
        {
          type: 'line',
          name: label,
          data: v,
          lineStyle: { width: 2, cap: 'round', join: 'round', color: GIZ },
          symbol: 'none',
          markLine: {
            silent: true,
            symbol: 'none',
            label: { show: false },
            lineStyle: { color: GRID },
            data: [{ yAxis: threshold }, { yAxis: -threshold }, { yAxis: 0 }],
          },
          markArea: { silent: true, data: phases },
          // rotulo direto SELETIVO: so o ultimo ponto (DESIGN.md §5)
          markPoint: {
            symbol: 'circle',
            symbolSize: 8,
            itemStyle: { color: diverging(0.5 + last.value / 6), borderColor: GIZ, borderWidth: 2 },
            label: { color: GIZ, position: 'right', formatter: () => last.value.toFixed(2) },
            // `name` e obrigatorio em MarkPointDataItemOption. Nao aparece na
            // tela (o formatter do label ignora), mas o tipo exige e o ECharts
            // usa internamente para identificar a marca.
            data: [{ name: 'ultimo', coord: [x[x.length - 1], last.value] }],
          },
        },
      ],
    };
  }, [points, threshold, label]);

  return (
    <EChart
      option={option}
      height={height}
      ariaLabel={`Serie de ${label}, ${points.length} pontos, com faixas de fase acima de ${threshold}`}
    />
  );
}

/**
 * Radar dos modos climaticos — le o ESTADO INTEIRO num golpe de vista.
 * Eixo = percentil [0,1] por sinal; o poligono fora do anel de 0.5 mostra
 * quantos modos estao simultaneamente em fase extrema.
 */
export function ModesRadar({ channels, height = 280 }: { channels: StateBlock[]; height?: number }) {
  const option = useMemo<EChartsOption>(
    () => ({
      animation: !reducedMotion,
      tooltip: {
        trigger: 'item',
        formatter: () =>
          channels.map((c) => `${c.label}: ${c.percentile.toFixed(2)}`).join('<br/>'),
      },
      radar: {
        indicator: channels.map((c) => ({ name: c.label, max: 1, min: 0 })),
        splitLine: { lineStyle: { color: GRID } },
        splitArea: { show: false },
        axisLine: { lineStyle: { color: GRID } },
        axisName: { color: BRUMA, fontSize: 10 },
        radius: '62%',
      },
      series: [
        {
          type: 'radar',
          symbolSize: 8,
          data: [
            {
              value: channels.map((c) => c.percentile),
              name: 'percentil atual',
              lineStyle: { width: 2, color: GIZ },
              itemStyle: { color: GIZ, borderColor: GIZ, borderWidth: 2 },
              areaStyle: { color: alpha(GIZ, 0.1) },
            },
            {
              // anel de referencia: mediana historica
              value: channels.map(() => 0.5),
              name: 'mediana',
              lineStyle: { width: 1, color: GRID },
              itemStyle: { color: 'transparent' },
              symbol: 'none',
            },
          ],
        },
      ],
      legend: { bottom: 0, data: ['percentil atual', 'mediana'] },
    }),
    [channels],
  );
  return <EChart option={option} height={height} ariaLabel="Radar dos modos climaticos por percentil" />;
}

/**
 * Trilha de 12 meses como faixa divergente por canal — versao em grafico da
 * Regua de Surpresa, com tooltip por celula.
 */
export function TrailStrip({ channel, height = 34 }: { channel: StateBlock; height?: number }) {
  const option = useMemo<EChartsOption>(() => {
    const trail = (channel.trail_12m.length ? channel.trail_12m : [channel.percentile]).slice(-12);
    return {
      animation: !reducedMotion,
      grid: { left: 0, right: 0, top: 2, bottom: 2 },
      xAxis: { type: 'category', show: false, data: trail.map((_, i) => `m-${trail.length - i}`) },
      yAxis: { type: 'value', show: false, max: 1 },
      tooltip: {
        trigger: 'item',
        formatter: (p: unknown) => {
          const { dataIndex } = p as { dataIndex: number };
          return `${channel.label}<br/>percentil ${trail[dataIndex].toFixed(2)}`;
        },
      },
      series: [
        {
          type: 'bar',
          data: trail.map((t) => ({ value: 1, itemStyle: { color: diverging(t) } })),
          // gap de 2px na cor da superficie separa as marcas (DESIGN.md §5)
          barCategoryGap: '4%',
          itemStyle: { borderRadius: 1 },
        },
      ],
    };
  }, [channel]);
  return <EChart option={option} height={height} ariaLabel={`Trilha de 12 meses de ${channel.label}`} />;
}
