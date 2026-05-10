'use client';

import React from 'react';
import { StatusDot, NavMetric } from './primitives';
import { fmtTime } from '@/lib/mock-data';

export function TopBar({
  now,
  live,
  qps,
  fps,
  todayHigh,
}: {
  now: Date;
  live: boolean;
  qps: string;
  fps: number;
  todayHigh: number;
}) {
  const NAV_ITEMS = ['DASHBOARD', 'PROFILE', 'AB EVAL', 'MODELS', 'LOGS'];

  return (
    <header className="h-[50px] bg-bg-1 border-b border-line flex items-stretch">
      {/* Logo area */}
      <div className="px-[18px] flex items-center gap-3 border-r border-line">
        <div className="w-[22px] h-[22px] relative">
          <div className="absolute inset-0 border border-sig-cyan" />
          <div className="absolute inset-1 bg-sig-cyan/30" />
          <div className="absolute-[7px] bg-sig-cyan" style={{ position: 'absolute', inset: 7 }} />
        </div>
        <div>
          <div className="font-mono text-xs font-bold text-fg tracking-[0.04em]">
            EDGE.PROFILER<span className="text-sig-cyan">/</span>RK3588
          </div>
          <div className="font-mono text-[9px] text-fg-3 mt-px tracking-[0.1em]">
            v1.0.0 &middot; build 2026.05.02 &middot; 6 TOPS
          </div>
        </div>
      </div>

      {/* Nav tabs */}
      <nav className="flex items-stretch">
        {NAV_ITEMS.map((t, i) => (
          <a
            key={t}
            href="#"
            className="px-[18px] flex items-center border-r border-line font-mono text-[11px] tracking-[0.12em] no-underline"
            style={{
              color: i === 0 ? 'var(--color-fg)' : 'var(--color-fg-2)',
              fontWeight: i === 0 ? 700 : 500,
              background: i === 0 ? 'var(--color-bg-2)' : 'transparent',
              borderBottom: i === 0 ? '2px solid var(--color-sig-cyan)' : '2px solid transparent',
            }}
          >
            {t}
          </a>
        ))}
      </nav>

      <div className="flex-1" />

      {/* Right metrics */}
      <div className="flex items-center gap-[18px] px-[18px]">
        <NavMetric label="QPS" value={qps} color="var(--color-sig-cyan)" />
        <NavMetric label="FPS" value={fps.toFixed(2)} color="var(--color-sig-amber)" />
        <NavMetric label="HIGH" value={todayHigh} color="var(--color-sig-red)" />
        <span className="w-px h-6 bg-line" />
        <span className="font-mono text-[11px] text-fg tabular-nums">
          {fmtTime(now)}<span className="text-fg-3"> UTC+8</span>
        </span>
        <StatusDot state={live ? 'online' : 'stale'} />
      </div>
    </header>
  );
}
