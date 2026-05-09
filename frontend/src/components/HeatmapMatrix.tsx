'use client';

import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';

interface Props {
  matrix: Record<string, Record<string, number>>;
}

const SEVERITIES = ['low', 'medium', 'high'];
const CATEGORIES = ['metal_nut', 'screw', 'pill'];

export default function HeatmapMatrix({ matrix }: Props) {
  const { data, maxVal } = useMemo(() => {
    let max = 0;
    const d: number[][] = [];
    for (let yi = 0; yi < CATEGORIES.length; yi++) {
      for (let xi = 0; xi < SEVERITIES.length; xi++) {
        const val = matrix[CATEGORIES[yi]]?.[SEVERITIES[xi]] ?? 0;
        d.push([xi, yi, val]);
        if (val > max) max = val;
      }
    }
    return { data: d, maxVal: Math.max(max, 1) };
  }, [matrix]);

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      position: 'top',
      backgroundColor: '#161a23',
      borderColor: '#2a3142',
      textStyle: { color: '#e6ebf5', fontFamily: "'JetBrains Mono', monospace", fontSize: 11 },
      formatter: (p: { value: number[] }) =>
        `${CATEGORIES[p.value[1]]} / ${SEVERITIES[p.value[0]]}: ${p.value[2]}`,
    },
    grid: { top: '8%', bottom: '18%', left: '22%', right: '8%' },
    xAxis: {
      type: 'category',
      data: ['Low', 'Medium', 'High'],
      axisLabel: { color: '#7d869c', fontFamily: "'JetBrains Mono', monospace", fontSize: 11 },
      splitArea: { show: true, areaStyle: { color: ['transparent', 'rgba(255,255,255,0.02)'] } },
    },
    yAxis: {
      type: 'category',
      data: CATEGORIES,
      axisLabel: { color: '#7d869c', fontFamily: "'JetBrains Mono', monospace", fontSize: 11 },
      splitArea: { show: true, areaStyle: { color: ['transparent', 'rgba(255,255,255,0.02)'] } },
    },
    visualMap: {
      min: 0,
      max: maxVal,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: '-2%',
      inRange: { color: ['#0f1218', '#5ad6ff'] },
      textStyle: { color: '#555d72', fontFamily: "'JetBrains Mono', monospace", fontSize: 10 },
    },
    series: [
      {
        name: 'Defects',
        type: 'heatmap',
        data,
        label: { show: true, color: '#e6ebf5', fontFamily: "'JetBrains Mono', monospace", fontSize: 11 },
        emphasis: {
          itemStyle: { shadowBlur: 6, shadowColor: 'rgba(90, 214, 255, 0.4)' },
        },
      },
    ],
  };

  return (
    <div className="bg-bg-1 border border-line rounded-lg p-5">
      <h3 className="text-sm font-semibold text-fg mb-1">Category x Severity Matrix</h3>
      <ReactECharts option={option} style={{ height: 240, width: '100%' }} />
    </div>
  );
}
