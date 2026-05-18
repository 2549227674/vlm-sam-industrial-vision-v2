'use client';

import React from 'react';
import { fmtNumber } from '@/lib/mock-data';
import type { MockAbMetrics } from '@/lib/mock-data';

interface MetricDef {
  id: string;
  label: string;
  a: number;
  b: number;
  unit: string;
  hi: 'low' | 'high';
  digits: number;
  max: number;
}

export function ABCompare({
  aStats,
  bStats,
  focus = 'ttft',
}: {
  aStats: MockAbMetrics;
  bStats: MockAbMetrics;
  focus?: string;
}) {
  const metrics: MetricDef[] = [
    { id: 'ttft', label: 'First-Token Latency', a: aStats.avg_ttft_ms, b: bStats.avg_ttft_ms, unit: 'ms', hi: 'low', digits: 0, max: 2800 },
    { id: 'json', label: 'JSON Parse OK', a: aStats.json_ok_rate * 100, b: bStats.json_ok_rate * 100, unit: '%', hi: 'high', digits: 1, max: 100 },
    { id: 'tps', label: 'Decode Throughput', a: aStats.avg_decode_tps, b: bStats.avg_decode_tps, unit: 'tok/s', hi: 'high', digits: 2, max: 14 },
    { id: 'rss', label: 'Runtime RSS', a: aStats.avg_rss_mb, b: bStats.avg_rss_mb, unit: 'MB', hi: 'low', digits: 0, max: 3500 },
    { id: 'ptok', label: 'Prompt Tokens', a: 1140, b: 78, unit: 'tok', hi: 'low', digits: 0, max: 1500 },
  ];

  const thCls = 'font-mono text-[9px] font-medium tracking-[0.16em] text-fg-3 px-3.5 py-0 border-b border-line text-left';
  const tdCls = 'px-3.5 py-2.5 align-middle';

  return (
    <div>
      {/* Headers */}
      <div className="grid grid-cols-2 border-b border-line">
        <ABHeader
          side="A"
          color="var(--color-sig-violet)"
          title="BASE + LONG PROMPT"
          sub="Qwen3-VL-2B · few-shot + JSON schema · ~1140 tok"
          count={aStats.count}
        />
        <ABHeader
          side="B"
          color="var(--color-sig-teal)"
          title="LoRA r16 + MINIMAL PROMPT"
          sub="MVTec AD finetune · prompt ≤ 100 tok"
          count={bStats.count}
          winner
        />
      </div>

      {/* Table */}
      <table className="w-full border-collapse font-sans">
        <thead>
          <tr className="bg-bg-2 h-8">
            <th className={thCls}>METRIC</th>
            <th className={`${thCls} text-right text-sig-violet`}>A</th>
            <th className={thCls}></th>
            <th className={`${thCls} text-right text-sig-teal`}>B</th>
            <th className={`${thCls} text-right`}>Δ B vs A</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map(m => {
            const delta = m.b - m.a;
            const pct = m.a !== 0 ? (delta / m.a) * 100 : 0;
            const better = m.hi === 'high' ? delta > 0 : delta < 0;
            const pa = Math.min(1, m.a / m.max);
            const pb = Math.min(1, m.b / m.max);
            const winnerBg = m.id === focus ? 'var(--color-bg-3)' : 'transparent';

            return (
              <tr
                key={m.id}
                className="border-b border-line-soft h-[50px]"
                style={{ background: winnerBg }}
              >
                <td className={tdCls}>
                  <div className="text-xs text-fg font-medium">{m.label}</div>
                  <div className="font-mono text-[9px] text-fg-3 mt-px">
                    {m.hi === 'low' ? '↓ lower is better' : '↑ higher is better'}
                  </div>
                </td>
                <td className={`${tdCls} text-right w-[26%]`}>
                  <div className="flex items-center gap-2 justify-end">
                    <div className="flex-1 h-1 bg-bg-3 max-w-[100px]">
                      <div className="h-full bg-sig-violet" style={{ width: `${pa * 100}%` }} />
                    </div>
                    <span className="font-mono text-sm text-fg tabular-nums min-w-[60px]">
                      {fmtNumber(m.a, { digits: m.digits })}
                    </span>
                  </div>
                </td>
                <td className={`${tdCls} text-center w-6 text-fg-3`}>vs</td>
                <td className={`${tdCls} text-right w-[26%]`}>
                  <div className="flex items-center gap-2 justify-end">
                    <div className="flex-1 h-1 bg-bg-3 max-w-[100px]">
                      <div className="h-full bg-sig-teal" style={{ width: `${pb * 100}%` }} />
                    </div>
                    <span className="font-mono text-base text-fg tabular-nums font-semibold min-w-[60px]">
                      {fmtNumber(m.b, { digits: m.digits })}
                    </span>
                  </div>
                </td>
                <td className={`${tdCls} text-right w-[130px]`}>
                  <span
                    className="font-mono inline-block px-2 py-0.5 text-[11px] font-semibold"
                    style={{
                      border: `1px solid ${better ? 'var(--color-sig-green)' : 'var(--color-sig-red)'}`,
                      color: better ? 'var(--color-sig-green)' : 'var(--color-sig-red)',
                      background: `color-mix(in srgb, ${better ? 'var(--color-sig-green)' : 'var(--color-sig-red)'} 12%, transparent)`,
                    }}
                  >
                    {delta > 0 ? '+' : ''}{Math.abs(pct) < 1000 ? pct.toFixed(1) : Math.round(pct)}%
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Footer */}
      <div className="px-3.5 py-2.5 bg-bg-2 border-t border-line flex justify-between items-center">
        <span className="font-mono text-[10px] text-fg-3">
          eval n=<span className="text-fg">{aStats.count + bStats.count}</span> · stratified 70/30 split · MVTec test set
        </span>
        <span className="font-mono text-[10px] text-sig-teal">
          → DECISION: ship variant B for production
        </span>
      </div>
    </div>
  );
}

function ABHeader({
  side,
  title,
  sub,
  color,
  count,
  winner,
}: {
  side: string;
  title: string;
  sub: string;
  color: string;
  count: number;
  winner?: boolean;
}) {
  return (
    <div className="px-[18px] py-3.5 border-r border-line relative">
      <div className="flex items-center gap-2.5">
        <span
          className="w-7 h-7 border inline-flex items-center justify-center font-mono text-sm font-bold"
          style={{
            borderColor: color,
            color,
            background: `color-mix(in srgb, ${color} 14%, transparent)`,
          }}
        >
          {side}
        </span>
        <div>
          <div className="text-[13px] font-semibold text-fg">{title}</div>
          <div className="font-mono text-[10px] text-fg-3 mt-px">{sub}</div>
        </div>
      </div>
      <div className="flex justify-between items-baseline mt-2.5 gap-3">
        <span className="font-mono text-[9px] text-fg-3">n = {count}</span>
        {winner && (
          <span
            className="font-mono text-[9px] px-1.5 py-px font-semibold tracking-[0.14em]"
            style={{
              border: `1px solid ${color}`,
              color,
              background: `color-mix(in srgb, ${color} 12%, transparent)`,
            }}
          >
            ★ WINNER · 4 of 5 axes
          </span>
        )}
      </div>
    </div>
  );
}
