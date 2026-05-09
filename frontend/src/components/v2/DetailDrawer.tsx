'use client';

import React from 'react';
import { CategoryChip, SeverityChip, VariantChip } from './primitives';
import { fmtTime, fmtDateTime } from '@/lib/mock-data';
import { API_BASE } from '@/lib/api';
import type { DefectRead } from '@/types/defect';

export function DetailDrawer({
  defect,
  onClose,
}: {
  defect: DefectRead;
  onClose: () => void;
}) {
  if (!defect) return null;

  const total = Math.round(
    defect.pipeline_ms.efficientad + defect.pipeline_ms.fastsam + defect.pipeline_ms.qwen3vl
  );
  const stages = [
    { k: 'efficientad' as const, name: 'EfficientAD-S', color: 'var(--color-stage-1)' },
    { k: 'fastsam' as const, name: 'FastSAM-s', color: 'var(--color-stage-2)' },
    { k: 'qwen3vl' as const, name: 'Qwen3-VL-2B', color: 'var(--color-stage-3)' },
  ];

  return (
    <div className="bg-bg-1 border border-line flex flex-col">
      {/* Header */}
      <div className="px-3.5 py-2.5 border-b border-line bg-bg-2 flex justify-between items-center">
        <div className="flex items-center gap-2.5">
          <span className="font-mono text-sig-cyan text-[11px] font-bold">
            DEFECT #{defect.id}
          </span>
          <span className="w-px h-3 bg-line" />
          <CategoryChip value={defect.category} />
          <SeverityChip value={defect.severity} size="sm" />
          <VariantChip value={defect.variant} size="sm" />
        </div>
        <button
          onClick={onClose}
          className="bg-transparent border border-line text-fg-2 font-mono text-[10px] px-2 py-0.5 cursor-pointer tracking-[0.1em]"
        >
          CLOSE ESC
        </button>
      </div>

      {/* Frame + bbox */}
      <div className="p-3.5">
        <DefectFrame defect={defect} />
      </div>

      {/* VLM Output + Metrics */}
      <div className="grid grid-cols-2 gap-px bg-line">
        {/* VLM Output */}
        <div className="px-3.5 py-3 bg-bg-1">
          <div className="flex items-baseline gap-2 mb-2">
            <span className="font-mono text-[9px] font-medium tracking-[0.14em] uppercase text-fg-3">VLM OUTPUT</span>
            <span className="font-mono text-[9px] text-fg-3">&middot; parsed JSON</span>
          </div>
          <pre className="font-mono text-[11px] text-fg leading-relaxed whitespace-pre-wrap break-words m-0">
            {JSON.stringify({
              category: defect.category,
              defect_type: defect.defect_type,
              severity: defect.severity,
              confidence: defect.confidence,
              bboxes: defect.bboxes.map(b => ({
                x: +b.x.toFixed(3),
                y: +b.y.toFixed(3),
                w: +b.w.toFixed(3),
                h: +b.h.toFixed(3),
              })),
              description: defect.description,
            }, null, 2)}
          </pre>
        </div>

        {/* VLM Metrics */}
        <div className="px-3.5 py-3 bg-bg-1">
          <div className="flex items-baseline gap-2 mb-2">
            <span className="font-mono text-[9px] font-medium tracking-[0.14em] uppercase text-fg-3">VLM METRICS</span>
            <span className="font-mono text-[9px] text-fg-3">&middot; variant {defect.variant}</span>
          </div>
          <div className="grid grid-cols-2 gap-y-2.5">
            <KV label="TTFT" value={defect.vlm_metrics?.ttft_ms ?? 0} unit="ms" tone={defect.variant === 'B' ? 'teal' : 'violet'} />
            <KV label="DECODE" value={(defect.vlm_metrics?.decode_tps ?? 0).toFixed(2)} unit="tok/s" />
            <KV label="PROMPT TOK" value={defect.vlm_metrics?.prompt_tokens ?? 0} />
            <KV label="OUTPUT TOK" value={defect.vlm_metrics?.output_tokens ?? 0} />
            <KV label="RSS" value={defect.vlm_metrics?.rss_mb ?? 0} unit="MB" />
            <KV
              label="JSON PARSE"
              value={defect.vlm_metrics?.json_parse_ok ? 'OK' : 'FAIL'}
              tone={defect.vlm_metrics?.json_parse_ok ? 'green' : 'red'}
            />
          </div>
        </div>
      </div>

      {/* Pipeline gantt */}
      <div className="px-3.5 py-3 border-t border-line">
        <div className="font-mono text-[9px] font-medium tracking-[0.14em] uppercase text-fg-3 mb-2">
          3-STAGE PIPELINE · TOTAL {total}ms
        </div>
        <div className="relative h-[22px] bg-bg-3 border border-line-soft">
          {(() => {
            let acc = 0;
            return stages.map(s => {
              const ms = defect.pipeline_ms[s.k];
              const x = (acc / total) * 100;
              const w = (ms / total) * 100;
              acc += ms;
              return (
                <div
                  key={s.k}
                  className="absolute top-0 h-full flex items-center justify-center overflow-hidden"
                  style={{
                    left: `${x}%`,
                    width: `${w}%`,
                    background: s.color,
                    opacity: 0.85,
                    borderRight: '1px solid var(--color-bg-0)',
                  }}
                >
                  {w > 8 && (
                    <span className="font-mono text-[10px] text-bg-0 font-bold">
                      {ms < 100 ? ms.toFixed(1) : Math.round(ms)}
                    </span>
                  )}
                </div>
              );
            });
          })()}
        </div>
        <div className="grid grid-cols-3 mt-1.5">
          {stages.map(s => (
            <div key={s.k} className="flex items-center gap-1.5">
              <span className="w-2 h-2" style={{ background: s.color }} />
              <span className="font-mono text-[9px] text-fg-3">{s.name}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Provenance footer */}
      <div className="px-3.5 py-2.5 bg-bg-2 border-t border-line grid grid-cols-2 gap-1.5 font-mono text-[10px] text-fg-3">
        <div>line_id <span className="text-fg">{defect.line_id}</span></div>
        <div>edge_ts <span className="text-fg">{fmtDateTime(defect.edge_ts)}</span></div>
        <div>image_url <span className="text-fg">…/{defect.image_url.split('/').slice(-1)[0]}</span></div>
        <div>anomaly_score <span className="text-sig-amber">{defect.anomaly_score}</span></div>
      </div>
    </div>
  );
}

// DefectFrame — image with bbox overlay and scan-line aesthetic
function DefectFrame({ defect }: { defect: DefectRead }) {
  const sevColor =
    defect.severity === 'high' ? 'var(--color-sev-high)'
    : defect.severity === 'medium' ? 'var(--color-sev-med)'
    : 'var(--color-sev-low)';

  return (
    <div className="relative w-full aspect-[3/2] bg-bg-0 border border-line overflow-hidden">
      {/* Actual image */}
      <img
        src={`${API_BASE}${defect.image_url}`}
        alt="defect"
        className="absolute inset-0 w-full h-full object-cover"
      />

      {/* Scan-line overlay effect */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'repeating-linear-gradient(0deg, transparent 0, transparent 2px, rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px)',
        }}
      />

      {/* Corner readouts */}
      <div className="absolute top-2 left-2.5 font-mono text-[9px] text-sig-cyan tracking-[0.1em]">
        CAM-{defect.line_id} &middot; 1280×1024 &middot; {fmtTime(defect.edge_ts)}
      </div>
      <div className="absolute top-2 right-2.5 font-mono text-[9px] text-sig-amber">
        ANOMALY {defect.anomaly_score} &middot; σ
      </div>
      <div className="absolute bottom-2 left-2.5 font-mono text-[9px] text-fg-2">
        {defect.image_url.split('/').slice(-1)[0]}
      </div>
      <div className="absolute bottom-2 right-2.5 flex items-center gap-1.5 font-mono text-[9px] text-sig-green">
        <span
          className="w-[5px] h-[5px] rounded-full"
          style={{ background: 'var(--color-sig-green)', animation: 'pulse-dot 1.4s infinite' }}
        />
        REC
      </div>

      {/* Bounding boxes with corner ticks */}
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        className="absolute inset-0 w-full h-full"
      >
        {defect.bboxes.map((b, i) => {
          const x = b.x * 100, y = b.y * 100, w = b.w * 100, h = b.h * 100;
          const tick = 1.6;
          return (
            <g key={i}>
              {/* Corner ticks */}
              <polyline points={`${x},${y + tick} ${x},${y} ${x + tick},${y}`} stroke={sevColor} strokeWidth="0.3" fill="none" vectorEffect="non-scaling-stroke" />
              <polyline points={`${x + w - tick},${y} ${x + w},${y} ${x + w},${y + tick}`} stroke={sevColor} strokeWidth="0.3" fill="none" vectorEffect="non-scaling-stroke" />
              <polyline points={`${x},${y + h - tick} ${x},${y + h} ${x + tick},${y + h}`} stroke={sevColor} strokeWidth="0.3" fill="none" vectorEffect="non-scaling-stroke" />
              <polyline points={`${x + w - tick},${y + h} ${x + w},${y + h} ${x + w},${y + h - tick}`} stroke={sevColor} strokeWidth="0.3" fill="none" vectorEffect="non-scaling-stroke" />
              {/* Dashed rectangle */}
              <rect
                x={x} y={y} width={w} height={h}
                fill="none" stroke={sevColor}
                strokeWidth="0.15" strokeDasharray="0.6 0.4"
                vectorEffect="non-scaling-stroke" opacity={0.6}
              />
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// KV — key-value metric display
function KV({
  label,
  value,
  unit,
  tone = 'default',
}: {
  label: string;
  value: string | number;
  unit?: string;
  tone?: 'default' | 'cyan' | 'green' | 'amber' | 'red' | 'violet' | 'teal';
}) {
  const colorMap: Record<string, string> = {
    default: 'var(--color-fg)',
    cyan: 'var(--color-sig-cyan)',
    green: 'var(--color-sig-green)',
    amber: 'var(--color-sig-amber)',
    red: 'var(--color-sig-red)',
    violet: 'var(--color-sig-violet)',
    teal: 'var(--color-sig-teal)',
  };
  const c = colorMap[tone] ?? 'var(--color-fg)';

  return (
    <div>
      <div className="font-mono text-[9px] font-medium tracking-[0.14em] uppercase text-fg-3">{label}</div>
      <div className="flex items-baseline gap-1 mt-px">
        <span className="font-mono text-base font-medium tabular-nums" style={{ color: c }}>
          {value}
        </span>
        {unit && <span className="font-mono text-[9px] text-fg-3">{unit}</span>}
      </div>
    </div>
  );
}
