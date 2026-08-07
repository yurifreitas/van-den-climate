import { useMemo } from 'react';
import type { EChartsOption } from 'echarts';
import { EChart, GRID_BASE, reducedMotion } from './EChart';
import type { LedgerEntry } from '../../api/types';
import { BRUMA, BRUMA_FRACA, CARTA, ESTADO, GIZ, GRID, alpha, sequencial } from '../../theme/palette';

const TERCIL = ['Abaixo', 'Normal', 'Acima'];

/**
 * Matriz de contingencia previsto x observado.
 *
 * IMPORTANTE: isto e CONTAGEM, nao metrica de skill. Nenhum modelo passou a
 * ADR-007, entao RPSS/BSS continuam `null` e nao sao estimados aqui — mas a
 * contagem bruta do que foi previsto contra o que aconteceu e dado medido, e
 * sonegar isso deixava a tela vazia sem motivo. A diagonal e o acerto.
 */
export function ContingencyHeatmap({
  entries,
  height = 280,
}: {
  entries: LedgerEntry[];
  height?: number;
}) {
  const { option, hits, closed } = useMemo(() => {
    const m = [
      [0, 0, 0],
      [0, 0, 0],
      [0, 0, 0],
    ];
    let n = 0;
    entries.forEach((e) => {
      if (e.observed_tercile === null) return;
      m[e.predicted_tercile][e.observed_tercile] += 1;
      n += 1;
    });
    const acertos = m[0][0] + m[1][1] + m[2][2];
    const max = Math.max(1, ...m.flat());

    const data: [number, number, number][] = [];
    for (let p = 0; p < 3; p += 1) for (let o = 0; o < 3; o += 1) data.push([o, p, m[p][o]]);

    const opt: EChartsOption = {
      animation: !reducedMotion,
      grid: { ...GRID_BASE, left: 70, right: 24, top: 30, bottom: 44 },
      tooltip: {
        trigger: 'item',
        formatter: (q: unknown) => {
          const d = (q as { data: number[] }).data;
          const acerto = d[0] === d[1];
          return `previsto <b>${TERCIL[d[1]]}</b><br/>observado <b>${TERCIL[d[0]]}</b><br/>${d[2]} caso(s)${acerto ? ' · acerto' : ''}`;
        },
      },
      xAxis: {
        type: 'category',
        data: TERCIL,
        name: 'observado',
        nameLocation: 'middle',
        nameGap: 26,
        nameTextStyle: { color: BRUMA_FRACA },
        splitArea: { show: false },
      },
      yAxis: {
        type: 'category',
        data: TERCIL,
        name: 'previsto',
        nameTextStyle: { color: BRUMA_FRACA },
        splitArea: { show: false },
      },
      series: [
        {
          type: 'heatmap',
          data,
          label: {
            show: true,
            color: GIZ,
            fontSize: 13,
            formatter: (p: { data: number[] }) => (p.data[2] === 0 ? '—' : String(p.data[2])),
          },
          itemStyle: {
            // gap de 2px na cor da superficie separa as celulas
            borderColor: CARTA,
            borderWidth: 2,
            borderRadius: 2,
          },
          // rampa sequencial na diagonal (acerto) vs fora dela (erro):
          // magnitude por luminancia, identidade por matiz
          data_: undefined,
          emphasis: { itemStyle: { borderColor: GIZ } },
        },
      ],
      visualMap: {
        show: false,
        min: 0,
        max,
        inRange: { color: [sequencial(0), sequencial(0.5), sequencial(1)] },
      },
    };

    // cor por celula sobrepondo o visualMap: diagonal em verde, fora em cinza
    (opt.series as { data: unknown[] }[])[0].data = data.map(([o, p, c]) => ({
      value: [o, p, c],
      itemStyle: {
        color:
          c === 0
            ? alpha(GRID, 0.5)
            : o === p
              ? sequencial(0.25 + (0.75 * c) / max, ESTADO.ok)
              : sequencial(0.2 + (0.6 * c) / max, BRUMA_FRACA),
        borderColor: CARTA,
        borderWidth: 2,
        borderRadius: 2,
      },
    }));

    return { option: opt, hits: acertos, closed: n };
  }, [entries]);

  return (
    <>
      <EChart
        option={option}
        height={height}
        ariaLabel={`Matriz de contingencia: ${hits} acertos em ${closed} previsoes fechadas`}
      />
      <p className="t-note">
        {closed} previsoes fechadas · {hits} na diagonal ({closed ? Math.round((hits / closed) * 100) : 0}%
        de coincidencia bruta). Isto e CONTAGEM, nao skill: RPSS/BSS seguem sem valor porque nenhum
        modelo passou a ADR-007.
      </p>
    </>
  );
}

/**
 * Linha do tempo do ledger: cada previsao emitida como marca, cor pelo
 * desfecho (acerto / erro / ainda aberta). Mostra a coisa que a tabela
 * escondia — se os acertos se concentram num periodo ou estao espalhados.
 */
export function LedgerTimeline({ entries, height = 260 }: { entries: LedgerEntry[]; height?: number }) {
  const option = useMemo<EChartsOption>(() => {
    const targets = Array.from(new Set(entries.map((e) => e.target_id)));
    const points = entries.map((e) => {
      const aberta = e.observed_tercile === null;
      const acerto = !aberta && e.observed_tercile === e.predicted_tercile;
      return {
        value: [e.issued_at, targets.indexOf(e.target_id), e.predicted_tercile, e.observed_tercile ?? -1],
        itemStyle: {
          color: aberta ? 'transparent' : acerto ? ESTADO.ok : ESTADO.falha,
          borderColor: aberta ? BRUMA_FRACA : CARTA,
          borderWidth: 2,
          borderType: aberta ? ('dashed' as const) : ('solid' as const),
        },
      };
    });
    return {
      animation: !reducedMotion,
      grid: { ...GRID_BASE, left: 8, right: 24 },
      tooltip: {
        trigger: 'item',
        formatter: (q: unknown) => {
          const d = (q as { value: [string, number, number, number] }).value;
          const aberto = d[3] < 0;
          return [
            `<b>${targets[d[1]]}</b>`,
            `emitido ${d[0]}`,
            `previsto ${TERCIL[d[2]]}`,
            aberto ? 'ainda aberta' : `observado ${TERCIL[d[3]]}`,
            aberto ? '' : d[2] === d[3] ? '✓ acerto' : '✗ erro',
          ]
            .filter(Boolean)
            .join('<br/>');
        },
      },
      xAxis: { type: 'time', axisLabel: { formatter: '{yyyy}-{MM}' } },
      yAxis: {
        type: 'category',
        data: targets,
        axisLabel: { color: BRUMA, fontSize: 10 },
        splitLine: { show: true, lineStyle: { color: GRID } },
      },
      series: [{ type: 'scatter', data: points, symbolSize: 13 }],
    };
  }, [entries]);
  return <EChart option={option} height={height} ariaLabel="Linha do tempo das previsoes emitidas, por alvo e desfecho" />;
}

/**
 * Taxa de coincidencia por alvo — barra empilhada acerto/erro/aberta.
 * De novo: contagem, nunca skill.
 */
export function LedgerOutcomeBars({ entries, height = 200 }: { entries: LedgerEntry[]; height?: number }) {
  const option = useMemo<EChartsOption>(() => {
    const targets = Array.from(new Set(entries.map((e) => e.target_id)));
    const stat = targets.map((t) => {
      const rows = entries.filter((e) => e.target_id === t);
      return {
        acerto: rows.filter((e) => e.observed_tercile !== null && e.observed_tercile === e.predicted_tercile).length,
        erro: rows.filter((e) => e.observed_tercile !== null && e.observed_tercile !== e.predicted_tercile).length,
        aberta: rows.filter((e) => e.observed_tercile === null).length,
      };
    });
    const serie = (name: string, key: 'acerto' | 'erro' | 'aberta', color: string, dashed = false) => ({
      type: 'bar' as const,
      stack: 'total',
      name,
      data: stat.map((s) => s[key]),
      barWidth: 18,
      itemStyle: {
        color: dashed ? 'transparent' : color,
        borderColor: dashed ? BRUMA_FRACA : CARTA,
        // gap de 2px entre segmentos empilhados, na cor da superficie
        borderWidth: 2,
        borderType: dashed ? ('dashed' as const) : ('solid' as const),
      },
    });
    return {
      animation: !reducedMotion,
      grid: { ...GRID_BASE, left: 8 },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { bottom: 0 },
      xAxis: { type: 'value', minInterval: 1 },
      yAxis: { type: 'category', data: targets, axisLabel: { color: BRUMA, fontSize: 10 } },
      series: [
        serie('acerto', 'acerto', ESTADO.ok),
        serie('erro', 'erro', ESTADO.falha),
        serie('ainda aberta', 'aberta', BRUMA_FRACA, true),
      ],
    };
  }, [entries]);
  return <EChart option={option} height={height} ariaLabel="Desfecho das previsoes por alvo" />;
}
