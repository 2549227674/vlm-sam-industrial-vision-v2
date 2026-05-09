'use client';

import React from 'react';
import type { AbMetrics } from '@/types/stats';

interface MetricDef {
  label: string;
  va: number;
  vb: number;
  isLowerBetter: boolean;
  format: (v: number) => string;
}

export default function AbComparePanel({ a, b }: { a: AbMetrics; b: AbMetrics }) {
  const metrics: MetricDef[] = [
    { label: 'TTFT (ms)', va: a.avg_ttft_ms, vb: b.avg_ttft_ms, isLowerBetter: true, format: (v) => Math.round(v).toString() },
    { label: 'JSON Parse OK (%)', va: a.json_ok_rate * 100, vb: b.json_ok_rate * 100, isLowerBetter: false, format: (v) => v.toFixed(1) },
    { label: 'Decode (tok/s)', va: a.avg_decode_tps, vb: b.avg_decode_tps, isLowerBetter: false, format: (v) => v.toFixed(1) },
    { label: 'Runtime RSS (MB)', va: a.avg_rss_mb, vb: b.avg_rss_mb, isLowerBetter: true, format: (v) => Math.round(v).toString() },
    { label: 'Prompt Tokens', va: a.avg_prompt_tokens, vb: b.avg_prompt_tokens, isLowerBetter: true, format: (v) => Math.round(v).toString() },
  ];

  return (
    <div className="bg-bg-1 border border-line rounded-lg p-5 flex flex-col h-full">
      <div className="flex justify-between items-center mb-5">
        <h3 className="text-sm font-semibold text-fg">A/B Testing Impact</h3>
        <div className="flex gap-3">
          <span className="text-sig-violet font-mono text-[10px] border border-sig-violet px-1.5 py-0.5 bg-sig-violet/10 tracking-wider">BASE (A)</span>
          <span className="text-sig-teal font-mono text-[10px] border border-sig-teal px-1.5 py-0.5 bg-sig-teal/10 tracking-wider">LoRA (B)</span>
        </div>
      </div>

      {/* Column headers */}
      <div className="flex items-center border-b border-line pb-1.5 mb-2 text-[9px] font-mono text-fg-4 uppercase tracking-wider">
        <span className="w-1/3">Metric</span>
        <span className="w-1/5 text-center">A</span>
        <span className="w-1/5 text-center">B</span>
        <span className="w-1/5 text-right">Delta</span>
      </div>

      <div className="flex-1 space-y-2.5">
        {metrics.map((m, i) => {
          const denom = m.va === 0 ? 1 : m.va;
          const delta = ((m.vb - m.va) / denom) * 100;
          const isImproved = m.isLowerBetter ? delta < 0 : delta > 0;
          const colorClass = isImproved ? 'text-sev-low' : 'text-sev-high';
          const arrow = delta > 0 ? '↑' : delta < 0 ? '↓' : '—';

          return (
            <div key={i} className="flex items-center justify-between border-b border-line-soft pb-2">
              <span className="text-xs text-fg-2 font-mono w-1/3">{m.label}</span>
              <span className="text-xs font-mono text-fg-3 w-1/5 text-center">{m.format(m.va)}</span>
              <span className="text-xs font-mono font-bold text-fg w-1/5 text-center">{m.format(m.vb)}</span>
              <span className={`flex items-center justify-end w-1/5 font-mono text-[11px] font-semibold ${colorClass}`}>
                <span className="mr-0.5">{arrow}</span>
                {Math.abs(delta).toFixed(1)}%
              </span>
            </div>
          );
        })}
      </div>

      <div className="mt-5 pt-3 border-t border-line text-center bg-bg-2 rounded px-3 py-2">
        <span className="font-mono text-xs text-sig-cyan font-bold tracking-widest">
          {'→'} DECISION: SHIP VARIANT B
        </span>
      </div>
    </div>
  );
}
