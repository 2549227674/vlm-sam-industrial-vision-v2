'use client';

import React, { useEffect, useState, useMemo, useCallback } from 'react';
import type { DefectRead } from '@/types/defect';
import { API_BASE } from '@/lib/api';
import { useDefectWebSocket } from '@/lib/ws';
import {
  seedDefects,
  buildStats,
  buildTimeline,
  fmtTime,
  type MockStats,
} from '@/lib/mock-data';
import {
  Panel,
  StatusDot,
  INT8Badge,
  KPIStrip,
  PipelineWaterfall,
  NPUUtilization,
  CategorySeverityMatrix,
  ThroughputChart,
  ABCompare,
  LiveStream,
  DetailDrawer,
} from '@/components/v2';

export default function DashboardStats() {
  const [defects, setDefects] = useState<DefectRead[]>([]);
  const [selected, setSelected] = useState<DefectRead | null>(null);
  const [tick, setTick] = useState(0);
  const [now, setNow] = useState(new Date());
  const [useMock, setUseMock] = useState(false);
  const [abFocus, setAbFocus] = useState<'ttft' | 'json' | 'rss'>('ttft');

  // Fetch initial defects from API
  useEffect(() => {
    if (useMock) return;
    fetch(`${API_BASE}/api/defects?page_size=50&sort=-edge_ts`)
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then((json) => setDefects(json.items ?? []))
      .catch(() => setUseMock(true));
  }, [useMock]);

  // Seed mock data if API unavailable
  useEffect(() => {
    if (useMock && defects.length === 0) {
      setDefects(seedDefects(140));
    }
  }, [useMock, defects.length]);

  // Live event simulation (mock mode)
  useEffect(() => {
    if (!useMock) return;
    let cancelled = false;
    function loop() {
      if (cancelled) return;
      const d = seedDefects(1)[0];
      (d as DefectRead & { _new?: boolean })._new = true;
      setDefects(prev => [d, ...prev].slice(0, 240));
      setTick(t => t + 1);
      setTimeout(loop, 2500 + Math.random() * 4000);
    }
    const id = setTimeout(loop, 2200);
    return () => { cancelled = true; clearTimeout(id); };
  }, [useMock]);

  // WebSocket handler (live mode)
  const handleNewDefect = useCallback((defect: DefectRead) => {
    setDefects(prev => [defect, ...prev].slice(0, 240));
    setTick(t => t + 1);
  }, []);

  useDefectWebSocket(handleNewDefect);

  // Clock
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  // Build computed data
  const mockStats: MockStats = useMemo(() => buildStats(defects), [defects]);
  const timeline = useMemo(() => buildTimeline(defects), [defects]);
  const recent = useMemo(() => defects.slice(0, 40), [defects]);

  const avgTotal = recent.length
    ? recent.reduce((s, d) => s + d.pipeline_ms.efficientad + d.pipeline_ms.fastsam + d.pipeline_ms.qwen3vl, 0) / recent.length
    : 0;
  const fps = avgTotal > 0 ? 1000 / avgTotal : 0;
  const qps = (defects.filter(d => Date.now() - new Date(d.edge_ts).getTime() < 60_000).length / 60).toFixed(2);

  const live = !useMock;

  return (
    <>
      {/* Main grid */}
      <div
        className="flex-1 grid gap-px bg-line"
        style={{
          gridTemplateColumns: selected ? 'minmax(0,1fr) 460px' : '1fr',
        }}
      >
        <div className="flex flex-col gap-px bg-line min-w-0">
          {/* KPI strip */}
          <KPIStrip stats={mockStats} avgTotal={avgTotal} fps={fps} tick={tick} />

          {/* Hero — pipeline waterfall */}
          <Panel
            id="P-001"
            eyebrow="HERO"
            title="3-Stage Pipeline · Per-frame Latency Waterfall"
            hot="var(--color-sig-cyan)"
            padded={false}
            right={
              <>
                <span className="font-mono text-[10px] text-fg-3">
                  last <span className="text-fg">{Math.min(20, recent.length)}</span> frames
                </span>
                <StatusDot state="online" />
              </>
            }
            footer={
              <>
                <span>profiler · libnsys-style render</span>
                <span>
                  FPS = 1000 / Σpipeline = <span className="text-sig-cyan">{fps.toFixed(2)}</span>
                </span>
              </>
            }
          >
            <div className="px-3.5 pt-3.5">
              <PipelineWaterfall samples={recent.slice(0, 20)} height={290} />
            </div>
          </Panel>

          {/* Two column: NPU + Severity matrix */}
          <div className="grid grid-cols-2 gap-px bg-line">
            <Panel
              id="P-002"
              eyebrow="HARDWARE"
              title="RK3588 NPU · Real-time Utilization"
              right={<INT8Badge />}
              footer={
                <>
                  <span>polled @ 2 Hz</span>
                  <span>tick #{tick}</span>
                </>
              }
            >
              <NPUUtilization />
            </Panel>
            <Panel
              id="P-003"
              eyebrow="DISTRIBUTION"
              title="Defects by Category × Severity"
              right={
                <span className="font-mono text-[10px] text-fg-3">n = {mockStats.total}</span>
              }
              footer={
                <>
                  <span>aggregate · last 24h</span>
                  <span>updated {fmtTime(now)}</span>
                </>
              }
            >
              <CategorySeverityMatrix stats={mockStats} />
            </Panel>
          </div>

          {/* Throughput */}
          <Panel
            id="P-004"
            eyebrow="THROUGHPUT"
            title="Frame Volume · 24h Histogram"
            right={
              <span className="font-mono text-[10px] text-fg-3">
                bucket = 1h · cyan = total · red = high-severity overlay
              </span>
            }
            footer={
              <>
                <span>edge_ts based · server time-zone local</span>
                <span>n = {mockStats.total}</span>
              </>
            }
          >
            <ThroughputChart buckets={timeline} height={150} />
          </Panel>

          {/* AB Compare */}
          <Panel
            id="P-005"
            eyebrow="AB EXPERIMENT"
            title="LoRA finetune vs Base+Long-Prompt · 5-axis"
            hot="var(--color-sig-teal)"
            padded={false}
            right={
              <>
                {(['ttft', 'json', 'rss'] as const).map(f => (
                  <button
                    key={f}
                    onClick={() => setAbFocus(f)}
                    className="font-mono text-[10px] px-2 py-px cursor-pointer tracking-[0.1em]"
                    style={{
                      background: abFocus === f ? 'var(--color-sig-cyan)' : 'transparent',
                      color: abFocus === f ? 'var(--color-bg-0)' : 'var(--color-fg-2)',
                      border: `1px solid ${abFocus === f ? 'var(--color-sig-cyan)' : 'var(--color-line)'}`,
                      fontWeight: abFocus === f ? 700 : 500,
                    }}
                  >
                    {f.toUpperCase()}
                  </button>
                ))}
              </>
            }
            footer={
              <>
                <span>backed by /api/stats · ab_compare</span>
                <span>same MVTec test split</span>
              </>
            }
          >
            <ABCompare aStats={mockStats.ab_compare.A} bStats={mockStats.ab_compare.B} focus={abFocus} />
          </Panel>

          {/* Live stream */}
          <Panel
            id="P-006"
            eyebrow="STREAM"
            title="Live Defect Feed · WebSocket"
            padded={false}
            right={
              <>
                <span className="font-mono text-[10px] text-fg-3">
                  QPS <span className="text-sig-cyan">{qps}</span>
                </span>
                <StatusDot state={live ? 'online' : 'stale'} />
              </>
            }
            footer={
              <>
                <span>click row to open inspector</span>
                <span>show {Math.min(14, defects.length)} of {defects.length}</span>
              </>
            }
          >
            <LiveStream
              defects={defects}
              onSelect={setSelected}
              selectedId={selected?.id}
            />
          </Panel>
        </div>

        {/* Detail drawer */}
        {selected && (
          <DetailDrawer defect={selected} onClose={() => setSelected(null)} />
        )}
      </div>
    </>
  );
}
