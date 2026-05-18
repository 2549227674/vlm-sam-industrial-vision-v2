'use client';

import React from 'react';
import { fmtDateTime } from '@/lib/mock-data';

export function BottomStatus({
  now,
  qps,
  live,
  tick,
}: {
  now: Date;
  qps: string;
  live: boolean;
  tick: number;
}) {
  return (
    <footer className="h-7 bg-bg-1 border-t border-line flex items-center font-mono text-[10px] text-fg-3 tracking-[0.06em]">
      <span className="px-3.5 border-r border-line" style={{ color: live ? 'var(--color-sig-green)' : 'var(--color-sig-amber)' }}>
        ● WS /ws/dashboard
      </span>
      <span className="px-3.5 border-r border-line">edge_ts → server_ts · drift &lt; 220ms</span>
      <span className="px-3.5 border-r border-line">
        events <span className="text-fg">{tick}</span>
      </span>
      <span className="px-3.5 border-r border-line">
        qps <span className="text-sig-cyan">{qps}</span>
      </span>
      <span className="px-3.5 border-r border-line">db · vision.db (WAL)</span>
      <span className="flex-1" />
      <span className="px-3.5 border-l border-line">schema_version v1</span>
      <span className="px-3.5 border-l border-line">{fmtDateTime(now)}</span>
    </footer>
  );
}
