'use client';

import React from 'react';
import type { StatsResponse } from '@/types/stats';

export default function KpiCards({ stats }: { stats: StatsResponse | null }) {
  if (!stats) return null;

  const B = stats.ab_compare.B;

  const kpis = [
    { label: '24H DEFECTS', value: stats.total, unit: '' },
    { label: 'AVG PIPELINE', value: Math.round(stats.avg_pipeline_ms.qwen3vl), unit: 'ms' },
    { label: 'JSON OK RATE', value: (B.json_ok_rate * 100).toFixed(1), unit: '%', success: true },
    { label: 'TTFT (B)', value: Math.round(B.avg_ttft_ms), unit: 'ms' },
    { label: 'DECODE (B)', value: B.avg_decode_tps.toFixed(1), unit: 'tok/s' },
    { label: 'RSS (B)', value: Math.round(B.avg_rss_mb), unit: 'MB' },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {kpis.map((kpi, idx) => (
        <div key={idx} className="bg-bg-1 border border-line rounded-lg p-3 flex flex-col justify-center">
          <span className="text-fg-3 text-[9px] font-mono tracking-wider uppercase mb-1.5">
            {kpi.label}
          </span>
          <div className="flex items-baseline gap-1">
            <span className={`text-xl font-mono font-semibold ${kpi.success ? 'text-sev-low' : 'text-fg'}`}>
              {kpi.value}
            </span>
            <span className="text-fg-4 text-[10px] font-mono">{kpi.unit}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
