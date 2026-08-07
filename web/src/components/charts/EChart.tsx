import { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import {
  BarChart,
  LineChart,
  ScatterChart,
  HeatmapChart,
  GraphChart,
  SankeyChart,
  TreemapChart,
  RadarChart,
  GaugeChart,
  PieChart,
  CustomChart,
} from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  VisualMapComponent,
  TitleComponent,
  GraphicComponent,
  ToolboxComponent,
  CalendarComponent,
  PolarComponent,
  BrushComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsOption } from 'echarts';
import { BRUMA, BRUMA_FRACA, CARTA_ALTA, GIZ, GRID, LINHA } from '../../theme/palette';

/**
 * Wrapper unico sobre ECharts.
 *
 * POR QUE ECharts e nao Recharts: a central precisa de marcas que Recharts
 * nao tem — grafo de forca (clusters de referencia), sankey (atribuicao com e
 * sem ENSO), heatmap de calendario (cobertura estacao x ano), treemap, radar,
 * gauge, e zoom por brush em serie longa. Recharts cobre barra/linha e para
 * ai; a alternativa seria montar cada uma dessas a mao em D3.
 *
 * Import por modulo (`echarts/core` + charts especificos) e deliberado: o
 * bundle carrega so o que a aplicacao usa, nao a biblioteca inteira.
 *
 * O tema e registrado uma vez a partir dos tokens — nenhum componente repete
 * cor de eixo, grid ou tooltip.
 */

echarts.use([
  BarChart,
  LineChart,
  ScatterChart,
  HeatmapChart,
  GraphChart,
  SankeyChart,
  TreemapChart,
  RadarChart,
  GaugeChart,
  PieChart,
  CustomChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  VisualMapComponent,
  TitleComponent,
  GraphicComponent,
  ToolboxComponent,
  CalendarComponent,
  PolarComponent,
  BrushComponent,
  CanvasRenderer,
]);

const MONO = "'IBM Plex Mono', ui-monospace, monospace";

echarts.registerTheme('risco', {
  backgroundColor: 'transparent',
  textStyle: { fontFamily: MONO, fontSize: 11, color: BRUMA },
  title: { textStyle: { color: GIZ, fontFamily: MONO, fontSize: 12 } },
  legend: {
    textStyle: { color: BRUMA, fontFamily: MONO, fontSize: 11 },
    icon: 'rect',
    itemWidth: 10,
    itemHeight: 10,
  },
  tooltip: {
    backgroundColor: CARTA_ALTA,
    borderColor: LINHA,
    borderWidth: 1,
    textStyle: { color: GIZ, fontFamily: MONO, fontSize: 11 },
    // crosshair recessivo — a linha guia nunca compete com o dado
    axisPointer: { lineStyle: { color: BRUMA_FRACA, width: 1 }, crossStyle: { color: BRUMA_FRACA } },
  },
  // gridline 1px SOLIDA e recessiva (DESIGN.md §5) — nunca tracejada
  categoryAxis: {
    axisLine: { lineStyle: { color: LINHA } },
    axisTick: { lineStyle: { color: LINHA } },
    axisLabel: { color: BRUMA, fontFamily: MONO, fontSize: 10 },
    splitLine: { show: false, lineStyle: { color: GRID, type: 'solid' } },
  },
  valueAxis: {
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: BRUMA, fontFamily: MONO, fontSize: 10 },
    splitLine: { show: true, lineStyle: { color: GRID, type: 'solid' } },
  },
});

export function EChart({
  option,
  height = 260,
  onEvents,
  ariaLabel,
}: {
  option: EChartsOption;
  height?: number;
  onEvents?: Record<string, (params: unknown) => void>;
  /** Descricao textual do que o grafico mostra — o piso de acessibilidade. */
  ariaLabel?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, 'risco', { renderer: 'canvas' });
    chartRef.current = chart;
    // ResizeObserver e nao window.resize: painel dentro de grid muda de
    // largura sem a janela mudar, e o canvas ficava esticado.
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    // notMerge: uma troca de temporada nao deve deixar serie antiga viva
    chart.setOption(option, { notMerge: true });
    if (!onEvents) return;
    Object.entries(onEvents).forEach(([evt, handler]) => chart.on(evt, handler));
    return () => {
      Object.keys(onEvents).forEach((evt) => chart.off(evt));
    };
  }, [option, onEvents]);

  return (
    <div
      ref={ref}
      style={{ width: '100%', height }}
      role="img"
      aria-label={ariaLabel}
    />
  );
}

/** Animacao desligada quando o sistema pede movimento reduzido. */
export const reducedMotion =
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

/** Base comum de grid: respiro para eixo mono de 10px, sem sobra. */
export const GRID_BASE = { left: 48, right: 16, top: 24, bottom: 28, containLabel: true };
