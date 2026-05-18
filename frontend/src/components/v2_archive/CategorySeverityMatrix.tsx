'use client';

import React, { useState, useEffect } from 'react';
import { SeverityChip, CategoryChip } from './primitives';
import type { MockStats } from '@/lib/mock-data';

const CATS = ['metal_nut', 'screw', 'pill'];
const SEVS = ['low', 'medium', 'high'];

// Deterministic initial grid (all zeros — matches SSR)
function emptyGrid(): Record<string, Record<string, number>> {
  const g: Record<string, Record<string, number>> = {};
  for (const c of CATS) {
    g[c] = {};
    for (const s of SEVS) g[c][s] = 0;
  }
  return g;
}

function buildGrid(stats: MockStats): { grid: Record<string, Record<string, number>>; total: number; max: number } {
  const g: Record<string, Record<string, number>> = {};
  let t = 0;
  for (const c of CATS) {
    g[c] = {};
    for (const s of SEVS) {
      const base = (stats.by_category[c] ?? 0) / 3;
      const weight = s === 'high' ? 0.18 : s === 'medium' ? 0.30 : 0.52;
      const v = Math.floor(base * weight + Math.random() * 6);
      g[c][s] = v;
      t += v;
    }
  }
  const m = Math.max(...CATS.flatMap(c => SEVS.map(s => g[c][s])), 1);
  return { grid: g, total: t, max: m };
}

export function CategorySeverityMatrix({ stats }: { stats: MockStats }) {
  const [grid, setGrid] = useState(emptyGrid);
  const [total, setTotal] = useState(0);
  const [max, setMax] = useState(1);

  useEffect(() => {
    const { grid: g, total: t, max: m } = buildGrid(stats);
    setGrid(g);
    setTotal(t);
    setMax(m);
  }, [stats]);

  return (
    <div>
      <div className="grid gap-px bg-line" style={{ gridTemplateColumns: 'auto repeat(3, 1fr)' }}>
        <div className="bg-bg-1" />
        {SEVS.map(s => (
          <div key={s} className="bg-bg-2 px-2.5 py-2 text-center">
            <SeverityChip value={s} size="sm" />
          </div>
        ))}
        {CATS.map(c => (
          <React.Fragment key={c}>
            <div className="bg-bg-2 px-3 py-2.5 flex items-center gap-2">
              <CategoryChip value={c} />
              <span className="font-mono text-[11px] text-fg">{c}</span>
            </div>
            {SEVS.map(s => {
              const v = grid[c][s];
              const intensity = max > 0 ? v / max : 0;
              const color = s === 'high' ? 'var(--color-sev-high)' : s === 'medium' ? 'var(--color-sev-med)' : 'var(--color-sev-low)';
              return (
                <div
                  key={s}
                  className="px-3 py-3.5 text-center relative"
                  style={{
                    background: `color-mix(in srgb, ${color} ${intensity * 50}%, var(--color-bg-1))`,
                  }}
                >
                  <span
                    className="font-mono text-[17px] tabular-nums font-semibold"
                    style={{ color: intensity > 0.7 ? 'var(--color-bg-0)' : 'var(--color-fg)' }}
                  >
                    {v}
                  </span>
                </div>
              );
            })}
          </React.Fragment>
        ))}
      </div>
      <div className="mt-3 flex justify-between items-center">
        <span className="font-mono text-[10px] text-fg-3">category × severity · last 24h</span>
        <span className="font-mono text-[10px] text-fg" suppressHydrationWarning>Σ = {total}</span>
      </div>
    </div>
  );
}
