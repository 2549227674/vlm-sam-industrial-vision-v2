'use client';

import React, { useEffect, useState } from 'react';
import type { StatsResponse } from '@/types/stats';
import { API_BASE } from '@/lib/api';
import KpiCards from './KpiCards';
import WaterfallChart from './WaterfallChart';
import HeatmapMatrix from './HeatmapMatrix';
import AbComparePanel from './AbComparePanel';

const FALLBACK: StatsResponse = {
  total: 0,
  by_category: {},
  by_severity: {},
  timeline: [],
  ab_compare: {
    A: { count: 0, json_ok_rate: 0, avg_ttft_ms: 0, avg_decode_tps: 0, avg_rss_mb: 0, avg_prompt_tokens: 0 },
    B: { count: 0, json_ok_rate: 0, avg_ttft_ms: 0, avg_decode_tps: 0, avg_rss_mb: 0, avg_prompt_tokens: 0 },
  },
  avg_pipeline_ms: { efficientad: 0, fastsam: 0, qwen3vl: 0 },
  category_severity_matrix: {},
};

export default function DashboardStats() {
  const [stats, setStats] = useState<StatsResponse | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/stats`)
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then((data) => setStats(data))
      .catch(() => setStats(FALLBACK));
  }, []);

  if (!stats) {
    return (
      <div className="h-32 flex items-center justify-center font-mono text-fg-3 text-sm">
        Loading stats...
      </div>
    );
  }

  return (
    <div className="w-full flex flex-col gap-5">
      <KpiCards stats={stats} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <WaterfallChart pipeline={stats.avg_pipeline_ms} />
        <HeatmapMatrix matrix={stats.category_severity_matrix} />
      </div>

      <AbComparePanel a={stats.ab_compare.A} b={stats.ab_compare.B} />
    </div>
  );
}
