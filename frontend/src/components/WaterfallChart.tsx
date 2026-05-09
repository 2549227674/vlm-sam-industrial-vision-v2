'use client';

import React from 'react';
import ReactECharts from 'echarts-for-react';

interface Props {
  pipeline: { efficientad: number; fastsam: number; qwen3vl: number };
}

export default function WaterfallChart({ pipeline }: Props) {
  const stages = ['EfficientAD-S', 'FastSAM-s', 'Qwen3-VL-2B'];
  const values = [pipeline.efficientad, pipeline.fastsam, pipeline.qwen3vl];
  const bases = [0, values[0], values[0] + values[1]];

  const option = {
    backgroundColor: 'transparent',
    grid: { left: '3%', right: '4%', bottom: '10%', top: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      data: stages,
      axisLabel: { color: '#7d869c', fontFamily: "'JetBrains Mono', monospace", fontSize: 11 },
      axisLine: { lineStyle: { color: '#2a3142' } },
    },
    yAxis: {
      type: 'value',
      name: 'ms',
      nameTextStyle: { color: '#555d72', fontFamily: "'JetBrains Mono', monospace", fontSize: 10 },
      splitLine: { lineStyle: { color: '#1f2533', type: 'dashed' } },
      axisLabel: { color: '#7d869c', fontFamily: "'JetBrains Mono', monospace", fontSize: 10 },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#161a23',
      borderColor: '#2a3142',
      textStyle: { color: '#e6ebf5', fontFamily: "'JetBrains Mono', monospace", fontSize: 11 },
    },
    series: [
      {
        name: 'Placeholder',
        type: 'bar',
        stack: 'Total',
        itemStyle: { borderColor: 'transparent', color: 'transparent' },
        emphasis: { itemStyle: { borderColor: 'transparent', color: 'transparent' } },
        data: bases,
      },
      {
        name: 'Latency',
        type: 'bar',
        stack: 'Total',
        barWidth: '40%',
        label: {
          show: true,
          position: 'top',
          color: '#e6ebf5',
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11,
          formatter: '{c} ms',
        },
        data: [
          { value: values[0], itemStyle: { color: '#4ade80' } },
          { value: values[1], itemStyle: { color: '#fbbf24' } },
          { value: values[2], itemStyle: { color: '#f87171' } },
        ],
      },
    ],
  };

  return (
    <div className="bg-bg-1 border border-line rounded-lg p-5 relative">
      <h3 className="text-sm font-semibold text-fg mb-1">Inference Pipeline Latency Waterfall</h3>
      <div className="absolute top-4 right-5 bg-bg-2 border border-line px-2.5 py-1 rounded z-10">
        <span className="text-sig-cyan font-mono text-[10px] font-semibold">
          {'→'} opportunity: LoRA short-prompt {'→'} -45% TTFT
        </span>
      </div>
      <ReactECharts option={option} style={{ height: 240, width: '100%' }} />
    </div>
  );
}
