'use client';

import React, { useState, useEffect } from 'react';

interface CoreData {
  id: number;
  name: string;
  load: number;
  task: string;
  color: string;
}

const INITIAL_CORES: CoreData[] = [
  { id: 0, name: 'NPU CORE 0', load: 18, task: 'EfficientAD-S', color: 'var(--color-stage-1)' },
  { id: 1, name: 'NPU CORE 1', load: 42, task: 'FastSAM-s', color: 'var(--color-stage-2)' },
  { id: 2, name: 'NPU CORE 2', load: 78, task: 'Qwen3-VL-2B', color: 'var(--color-stage-3)' },
];

function computeLoads(): number[] {
  const now = Date.now();
  return [
    18 + (Math.sin(now / 800) * 8 + 8),
    42 + (Math.sin(now / 600) * 12 + 8),
    78 + (Math.sin(now / 1100) * 8 + 8),
  ];
}

export function NPUUtilization() {
  const [loads, setLoads] = useState<number[]>(INITIAL_CORES.map(c => c.load));

  useEffect(() => {
    setLoads(computeLoads());
    const id = setInterval(() => setLoads(computeLoads()), 500);
    return () => clearInterval(id);
  }, []);

  const cores = INITIAL_CORES.map((c, i) => ({ ...c, load: loads[i] ?? c.load }));

  return (
    <div className="flex flex-col gap-2.5">
      {cores.map(c => (
        <div key={c.id}>
          <div className="flex justify-between items-baseline mb-1">
            <span className="flex items-center gap-2">
              <span className="font-mono text-[9px] text-fg-3 tracking-[0.12em]">{c.name}</span>
              <span className="font-mono text-[11px] text-fg">{c.task}</span>
            </span>
            <span className="font-mono text-[13px] font-semibold tabular-nums" style={{ color: c.color }} suppressHydrationWarning>
              {Math.round(c.load)}<span className="text-fg-3 text-[10px]">%</span>
            </span>
          </div>
          <div className="h-2 bg-bg-3 border border-line-soft relative overflow-hidden">
            <div
              className="h-full transition-[width] duration-500"
              style={{
                width: `${c.load}%`,
                background: c.color,
                boxShadow: `0 0 8px ${c.color}`,
              }}
            />
            <div
              className="absolute inset-0 pointer-events-none"
              style={{
                background: 'repeating-linear-gradient(90deg, transparent 0, transparent 9px, rgba(0,0,0,0.15) 9px, rgba(0,0,0,0.15) 10px)',
              }}
            />
          </div>
        </div>
      ))}

      <div className="mt-1.5 pt-2.5 border-t border-dashed border-line-soft grid grid-cols-3 gap-3">
        <div>
          <div className="font-mono text-[9px] font-medium tracking-[0.14em] uppercase text-fg-3">SoC TEMP</div>
          <div className="font-mono text-sm text-sig-amber mt-px">
            62.4<span className="text-fg-3 text-[10px]">°C</span>
          </div>
        </div>
        <div>
          <div className="font-mono text-[9px] font-medium tracking-[0.14em] uppercase text-fg-3">POWER</div>
          <div className="font-mono text-sm text-fg mt-px">
            4.8<span className="text-fg-3 text-[10px]">W</span>
          </div>
        </div>
        <div>
          <div className="font-mono text-[9px] font-medium tracking-[0.14em] uppercase text-fg-3">LPDDR4</div>
          <div className="font-mono text-sm text-fg mt-px">
            9.2<span className="text-fg-3 text-[10px]">/16 GB</span>
          </div>
        </div>
      </div>
    </div>
  );
}
