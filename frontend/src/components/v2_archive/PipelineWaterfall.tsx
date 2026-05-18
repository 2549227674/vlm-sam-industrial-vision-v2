'use client';

import React, { useRef, useState, useEffect, useMemo } from 'react';
import { INT8Badge } from './primitives';
import type { DefectRead } from '@/types/defect';

export function PipelineWaterfall({
  samples,
  height = 290,
}: {
  samples: DefectRead[];
  height?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(900);

  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver((es) => {
      for (const e of es) setW(e.contentRect.width);
    });
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);

  const padL = 60, padR = 80, padT = 22, padB = 28;
  const innerW = Math.max(200, w - padL - padR);
  const innerH = height - padT - padB;
  const rowH = Math.max(8, Math.min(14, innerH / Math.max(1, samples.length)));
  const rows = samples.slice(0, Math.floor(innerH / rowH));

  const totals = rows.map(r => r.pipeline_ms.efficientad + r.pipeline_ms.fastsam + r.pipeline_ms.qwen3vl);
  const maxTotal = Math.max(...totals, 2800);
  const ticks: number[] = [];
  for (let t = 0; t <= maxTotal; t += 500) ticks.push(t);

  const stageColors = ['var(--color-stage-1)', 'var(--color-stage-2)', 'var(--color-stage-3)'];
  const stageLabels = ['EfficientAD-S', 'FastSAM-s', 'Qwen3-VL-2B'];

  const avgs = useMemo(() => {
    const keys: Array<'efficientad' | 'fastsam' | 'qwen3vl'> = ['efficientad', 'fastsam', 'qwen3vl'];
    return keys.map(k => {
      const sum = rows.reduce((s, r) => s + r.pipeline_ms[k], 0);
      return sum / Math.max(1, rows.length);
    });
  }, [rows]);

  const avgTotal = avgs.reduce((s, x) => s + x, 0);
  const xScale = (ms: number) => (ms / maxTotal) * innerW;

  return (
    <div ref={ref} className="w-full relative">
      <svg width={w} height={height} viewBox={`0 0 ${w} ${height}`}>
        {/* Grid + ticks */}
        {ticks.map((t, i) => {
          const x = padL + xScale(t);
          return (
            <g key={i}>
              <line
                x1={x} y1={padT} x2={x} y2={padT + innerH}
                stroke="var(--color-line-soft)"
                strokeDasharray={t === 0 ? '0' : '1 3'}
              />
              <text
                x={x} y={padT - 8}
                textAnchor="middle"
                fill="var(--color-fg-3)"
                style={{ fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '0.05em' }}
              >
                {t === 0 ? '0' : `${t}ms`}
              </text>
            </g>
          );
        })}

        {/* Row bars */}
        {rows.map((r, i) => {
          const y = padT + i * rowH;
          let acc = 0;
          const segs = [
            { ms: r.pipeline_ms.efficientad, color: 'var(--color-stage-1)' },
            { ms: r.pipeline_ms.fastsam, color: 'var(--color-stage-2)' },
            { ms: r.pipeline_ms.qwen3vl, color: 'var(--color-stage-3)' },
          ];
          return (
            <g key={r.id ?? i}>
              {segs.map((s, j) => {
                const x = padL + xScale(acc);
                const ww = xScale(s.ms);
                acc += s.ms;
                return (
                  <rect
                    key={j}
                    x={x} y={y + 1}
                    width={Math.max(0.5, ww)}
                    height={rowH - 2}
                    fill={s.color}
                    opacity={i === 0 ? 1 : 0.85}
                  />
                );
              })}
              {/* Row label on left */}
              {i % Math.ceil(rows.length / 6) === 0 && (
                <text
                  x={padL - 8} y={y + rowH / 2 + 3}
                  textAnchor="end"
                  fill="var(--color-fg-3)"
                  style={{ fontFamily: 'var(--font-mono)', fontSize: 9 }}
                >
                  #{r.id}
                </text>
              )}
              {/* Total ms on right */}
              {i < 8 && (
                <text
                  x={padL + xScale(segs[0].ms + segs[1].ms + segs[2].ms) + 6}
                  y={y + rowH / 2 + 3}
                  textAnchor="start"
                  fill={i === 0 ? 'var(--color-fg)' : 'var(--color-fg-3)'}
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 9,
                    fontWeight: i === 0 ? 600 : 400,
                  }}
                >
                  {Math.round(segs[0].ms + segs[1].ms + segs[2].ms)}ms
                </text>
              )}
            </g>
          );
        })}

        {/* "now" line at top */}
        <line
          x1={padL} y1={padT} x2={padL + innerW} y2={padT}
          stroke="var(--color-sig-cyan)" strokeWidth="1" opacity="0.4"
        />

        {/* Average overlay annotations */}
        {(() => {
          let acc = 0;
          return [0, 1, 2].map(i => {
            const x = padL + xScale(acc);
            acc += avgs[i];
            const xEnd = padL + xScale(acc);
            const xMid = (x + xEnd) / 2;
            return (
              <g key={i}>
                <line
                  x1={x} y1={padT + innerH + 4} x2={x} y2={padT + innerH + 10}
                  stroke={stageColors[i]} strokeWidth="1.5"
                />
                {i === 2 && (
                  <line
                    x1={xEnd} y1={padT + innerH + 4} x2={xEnd} y2={padT + innerH + 10}
                    stroke={stageColors[i]} strokeWidth="1.5"
                  />
                )}
                <text
                  x={xMid} y={padT + innerH + 22}
                  textAnchor="middle"
                  fill={stageColors[i]}
                  style={{ fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 600 }}
                >
                  {Math.round(avgs[i])}
                </text>
              </g>
            );
          });
        })()}
      </svg>

      {/* Bottleneck callout */}
      <div
        className="absolute right-3.5 top-2.5 w-[220px] bg-bg-2 border border-sig-red p-2.5"
      >
        <div className="font-mono text-[9px] font-medium tracking-[0.14em] uppercase text-sig-red">
          ⚠ BOTTLENECK DETECTED
        </div>
        <div className="flex items-baseline gap-1 mt-1.5">
          <span className="font-mono text-[22px] font-medium text-fg">
            {((avgs[2] / avgTotal) * 100).toFixed(1)}
            <span className="text-xs text-fg-3">%</span>
          </span>
        </div>
        <div className="font-mono text-[10px] text-fg mt-1">
          Qwen3-VL &middot; {Math.round(avgs[2])}ms avg
        </div>
        <div className="font-mono text-[9px] text-fg-3 mt-2 leading-relaxed">
          → opportunity: LoRA short-prompt<br />
          → -45% TTFT (variant B)
        </div>
      </div>

      {/* Stage legend at bottom */}
      <div className="grid grid-cols-3 border-t border-line mt-1">
        {[0, 1, 2].map(i => {
          const ms = avgs[i];
          const pct = (ms / avgTotal) * 100;
          const isBottleneck = i === 2;
          return (
            <div
              key={i}
              className="px-3.5 py-2.5 relative"
              style={{
                borderRight: i < 2 ? '1px solid var(--color-line)' : 'none',
                borderTop: `2px solid ${stageColors[i]}`,
                background: isBottleneck ? 'color-mix(in srgb, var(--color-sig-red) 5%, transparent)' : 'transparent',
              }}
            >
              <div className="flex justify-between items-baseline">
                <span className="flex items-center gap-1.5">
                  <span className="font-mono text-[9px] text-fg-3">STAGE {i + 1}</span>
                  <span className="font-mono text-[11px] text-fg font-semibold">{stageLabels[i]}</span>
                  <INT8Badge />
                </span>
                <span
                  className="font-mono text-[9px] font-semibold"
                  style={{ color: isBottleneck ? 'var(--color-sig-red)' : 'var(--color-fg-3)' }}
                >
                  {pct.toFixed(1)}%
                </span>
              </div>
              <div className="flex items-baseline gap-1 mt-2">
                <span
                  className="font-mono text-[22px] font-medium tabular-nums"
                  style={{ color: stageColors[i] }}
                >
                  {ms < 100 ? ms.toFixed(1) : Math.round(ms)}
                </span>
                <span className="font-mono text-[10px] text-fg-3">ms &middot; avg</span>
              </div>
              <div className="font-mono text-[9px] text-fg-3 mt-1">
                {i === 0 && 'PDN · 256×256 · NPU core 0'}
                {i === 1 && 'YOLOv8-seg · 640×640 · NPU 1'}
                {i === 2 && 'W8A8 · prompt+decode · NPU 2'}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
