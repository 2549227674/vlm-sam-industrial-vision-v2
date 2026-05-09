'use client';

import React, { useRef, useState, useEffect } from 'react';
import type { TimelineBucket } from '@/lib/mock-data';

export function ThroughputChart({
  buckets,
  height = 150,
  accent = 'var(--color-sig-cyan)',
}: {
  buckets: TimelineBucket[];
  height?: number;
  accent?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(700);

  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver((es) => {
      for (const e of es) setW(e.contentRect.width);
    });
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);

  const padL = 36, padR = 12, padT = 14, padB = 22;
  const innerW = Math.max(80, w - padL - padR);
  const innerH = height - padT - padB;
  const max = Math.max(...buckets.map(b => b.count), 1);
  const barW = innerW / buckets.length;

  return (
    <div ref={ref} className="w-full">
      <svg width={w} height={height} viewBox={`0 0 ${w} ${height}`}>
        {/* Grid lines */}
        {[0, 0.5, 1].map((p, i) => {
          const y = padT + (1 - p) * innerH;
          return (
            <g key={i}>
              <line
                x1={padL} y1={y} x2={padL + innerW} y2={y}
                stroke="var(--color-line-soft)"
                strokeDasharray={p === 0 ? '0' : '1 3'}
              />
              <text
                x={padL - 6} y={y + 3}
                textAnchor="end"
                fill="var(--color-fg-3)"
                style={{ fontFamily: 'var(--font-mono)', fontSize: 9 }}
              >
                {Math.round(max * p)}
              </text>
            </g>
          );
        })}

        {/* Bars */}
        {buckets.map((b, i) => {
          const h = (b.count / max) * innerH;
          const x = padL + i * barW;
          const y = padT + innerH - h;
          const isHi = b.hi > 0;
          return (
            <g key={i}>
              <rect
                x={x + 1} y={y}
                width={Math.max(1, barW - 2)}
                height={h}
                fill={isHi ? 'var(--color-sig-red)' : accent}
                opacity={i === buckets.length - 1 ? 1 : 0.7}
              />
              {b.hi > 0 && (
                <rect
                  x={x + 1} y={y}
                  width={Math.max(1, barW - 2)}
                  height={Math.min(h, (b.hi / b.count) * h)}
                  fill="var(--color-sig-red)"
                />
              )}
            </g>
          );
        })}

        {/* X-axis labels */}
        {buckets.map((b, i) => {
          if (i % 4 !== 0 && i !== buckets.length - 1) return null;
          const x = padL + i * barW + barW / 2;
          return (
            <text
              key={i} x={x} y={height - 6}
              textAnchor="middle"
              fill="var(--color-fg-3)"
              style={{ fontFamily: 'var(--font-mono)', fontSize: 9 }}
            >
              {String(b.ts.getHours()).padStart(2, '0')}:00
            </text>
          );
        })}

        {/* Live cursor */}
        <line
          x1={padL + innerW - 1} y1={padT}
          x2={padL + innerW - 1} y2={padT + innerH}
          stroke={accent} strokeWidth="1" opacity="0.6" strokeDasharray="2 2"
        />
      </svg>
    </div>
  );
}
