'use client';

import React from 'react';
import { MetricCell } from './primitives';
import type { MockStats } from '@/lib/mock-data';

export function KPIStrip({
  stats,
  avgTotal,
  fps,
  tick,
}: {
  stats: MockStats;
  avgTotal: number;
  fps: number;
  tick: number;
}) {
  const A = stats.ab_compare.A;
  const B = stats.ab_compare.B;

  return (
    <div className="grid grid-cols-6 bg-line gap-px">
      <MetricCell
        label="DEFECTS · 24h"
        value={stats.total}
        sub={`high · ${stats.today_high}`}
        flashKey={tick}
        tone="cyan"
      />
      <MetricCell
        label="AVG PIPELINE"
        value={Math.round(avgTotal)}
        unit="ms"
        sub={`fps · ${fps.toFixed(2)}`}
        tone="amber"
      />
      <MetricCell
        label="NPU CORE 2 · LOAD"
        value="78"
        unit="%"
        sub="Qwen3-VL pinned"
        tone="red"
      />
      <MetricCell
        label="JSON OK · B"
        value={`${(B.json_ok_rate * 100).toFixed(1)}`}
        unit="%"
        sub={`A · ${(A.json_ok_rate * 100).toFixed(1)}%`}
        tone="teal"
      />
      <MetricCell
        label="TTFT · B"
        value={Math.round(B.avg_ttft_ms)}
        unit="ms"
        sub={`-${Math.round((1 - B.avg_ttft_ms / A.avg_ttft_ms) * 100)}% vs A`}
        tone="green"
      />
      <MetricCell
        label="RSS · STEADY"
        value={Math.round(B.avg_rss_mb)}
        unit="MB"
        sub="of 16384 LPDDR4"
        tone="default"
      />
    </div>
  );
}
