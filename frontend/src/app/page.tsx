'use client';

import React, { useState, useEffect, useMemo } from 'react';
import DashboardStats from '@/components/DashboardStats';
import { TopBar, BottomStatus } from '@/components/v2';
import { buildStats, seedDefects } from '@/lib/mock-data';

export default function Dashboard() {
  const [now, setNow] = useState(new Date());
  const [tick] = useState(0);
  const [live] = useState(true);

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  // Build mock stats for TopBar/BottomStatus
  const mockDefects = useMemo(() => seedDefects(140), []);
  const stats = useMemo(() => buildStats(mockDefects), [mockDefects]);

  const avgTotal = mockDefects.length
    ? mockDefects.reduce((s, d) => s + d.pipeline_ms.efficientad + d.pipeline_ms.fastsam + d.pipeline_ms.qwen3vl, 0) / mockDefects.length
    : 0;
  const fps = avgTotal > 0 ? 1000 / avgTotal : 0;
  const qps = (mockDefects.filter(d => Date.now() - new Date(d.edge_ts).getTime() < 60_000).length / 60).toFixed(2);

  return (
    <div className="min-h-screen bg-bg-0 flex flex-col">
      <TopBar now={now} live={live} qps={qps} fps={fps} todayHigh={stats.today_high} />

      <DashboardStats />

      <BottomStatus now={now} qps={qps} live={live} tick={tick} />
    </div>
  );
}
