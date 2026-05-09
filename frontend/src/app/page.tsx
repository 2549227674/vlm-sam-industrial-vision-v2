'use client';

import React, { useState, useEffect, useMemo } from 'react';
import DashboardStats from '@/components/DashboardStats';
import { TopBar, BottomStatus } from '@/components/v2';
import { buildStats, seedDefects, type MockStats } from '@/lib/mock-data';
import type { DefectRead } from '@/types/defect';

const EMPTY_STATS: MockStats = {
  total: 0, today_defects: 0, today_high: 0,
  by_category: { metal_nut: 0, screw: 0, pill: 0 },
  by_severity: { low: 0, medium: 0, high: 0 },
  ab_compare: {
    A: { count: 0, json_ok: 0, json_ok_rate: 0, ttft: 0, avg_ttft_ms: 0, tps: 0, avg_decode_tps: 0, rss: 0, avg_rss_mb: 0 },
    B: { count: 0, json_ok: 0, json_ok_rate: 0, ttft: 0, avg_ttft_ms: 0, tps: 0, avg_decode_tps: 0, rss: 0, avg_rss_mb: 0 },
  },
};

export default function Dashboard() {
  const [now, setNow] = useState(new Date(0));
  const [tick] = useState(0);
  const [live] = useState(true);
  const [mockDefects, setMockDefects] = useState<DefectRead[]>([]);
  const [stats, setStats] = useState<MockStats>(EMPTY_STATS);

  // Clock — client-only
  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  // Mock data — client-only to avoid hydration mismatch
  useEffect(() => {
    const defects = seedDefects(140);
    setMockDefects(defects);
    setStats(buildStats(defects));
  }, []);

  const avgTotal = mockDefects.length
    ? mockDefects.reduce((s, d) => s + d.pipeline_ms.efficientad + d.pipeline_ms.fastsam + d.pipeline_ms.qwen3vl, 0) / mockDefects.length
    : 0;
  const fps = avgTotal > 0 ? 1000 / avgTotal : 0;
  const qps = mockDefects.length > 0
    ? (mockDefects.filter(d => Date.now() - new Date(d.edge_ts).getTime() < 60_000).length / 60).toFixed(2)
    : '0.00';

  return (
    <div className="min-h-screen bg-bg-0 flex flex-col">
      <TopBar now={now} live={live} qps={qps} fps={fps} todayHigh={stats.today_high} />

      <DashboardStats />

      <BottomStatus now={now} qps={qps} live={live} tick={tick} />
    </div>
  );
}
