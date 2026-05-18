'use client';

import React, { useState, useMemo } from 'react';
import { SeverityChip, CategoryChip, VariantChip } from './primitives';
import { fmtTime } from '@/lib/mock-data';
import type { DefectRead } from '@/types/defect';

export function LiveStream({
  defects,
  onSelect,
  selectedId,
}: {
  defects: DefectRead[];
  onSelect: (d: DefectRead) => void;
  selectedId?: number;
}) {
  const [filter, setFilter] = useState({ severity: 'all', variant: 'all', category: 'all' });

  const filtered = useMemo(() => {
    return defects.filter(d => {
      if (filter.severity !== 'all' && d.severity !== filter.severity) return false;
      if (filter.variant !== 'all' && d.variant !== filter.variant) return false;
      if (filter.category !== 'all' && d.category !== filter.category) return false;
      return true;
    });
  }, [defects, filter]);

  const PAGE = 14;
  const rows = filtered.slice(0, PAGE);

  const colStyle = 'grid grid-cols-[60px_80px_70px_50px_60px_1fr_100px_80px]';

  return (
    <div>
      {/* Filter bar */}
      <div className="flex gap-3.5 px-3.5 py-2.5 border-b border-line bg-bg-2 items-center">
        <FilterGroup
          label="SEV"
          value={filter.severity}
          onChange={v => setFilter({ ...filter, severity: v })}
          options={[['all', 'ALL'], ['high', 'HI'], ['medium', 'MED'], ['low', 'LOW']]}
        />
        <FilterGroup
          label="VAR"
          value={filter.variant}
          onChange={v => setFilter({ ...filter, variant: v })}
          options={[['all', 'A+B'], ['A', 'A'], ['B', 'B']]}
        />
        <FilterGroup
          label="CAT"
          value={filter.category}
          onChange={v => setFilter({ ...filter, category: v })}
          options={[['all', 'ALL'], ['metal_nut', 'MN'], ['screw', 'SCR'], ['pill', 'PIL']]}
        />
        <span className="flex-1" />
        <span className="font-mono text-[10px] text-fg-3">
          shown <span className="text-fg">{rows.length}</span> / {filtered.length}
        </span>
      </div>

      {/* Column header */}
      <div
        className={`${colStyle} px-3.5 py-1.5 border-b border-line bg-bg-1 font-mono text-[9px] text-fg-3 tracking-[0.14em] font-medium`}
      >
        <span>ID</span>
        <span>TIME</span>
        <span>SEVERITY</span>
        <span>VAR</span>
        <span>CAT</span>
        <span>DEFECT</span>
        <span className="text-right">TOTAL ms</span>
        <span className="text-right">CONF</span>
      </div>

      {/* Rows */}
      <div>
        {rows.map((d, i) => {
          const total = Math.round(d.pipeline_ms.efficientad + d.pipeline_ms.fastsam + d.pipeline_ms.qwen3vl);
          const isNew = i === 0 && (d as DefectRead & { _new?: boolean })._new;
          const isSel = d.id === selectedId;

          return (
            <div
              key={d.id}
              onClick={() => onSelect(d)}
              className={`${colStyle} px-3.5 py-[9px] border-b border-line-soft text-xs items-center cursor-pointer relative`}
              style={{
                background: isSel
                  ? 'color-mix(in srgb, var(--color-sig-cyan) 8%, var(--color-bg-1))'
                  : isNew
                    ? 'color-mix(in srgb, var(--color-sig-cyan) 4%, var(--color-bg-1))'
                    : i % 2 === 0 ? 'var(--color-bg-1)' : 'var(--color-bg-2)',
                borderLeft: isSel ? '2px solid var(--color-sig-cyan)' : '2px solid transparent',
                animation: isNew ? 'slide-in-toast 0.4s ease-out' : 'none',
              }}
              onMouseEnter={e => {
                if (!isSel) e.currentTarget.style.background = 'var(--color-bg-3)';
              }}
              onMouseLeave={e => {
                if (!isSel) {
                  e.currentTarget.style.background = i % 2 === 0 ? 'var(--color-bg-1)' : 'var(--color-bg-2)';
                }
              }}
            >
              <span className="font-mono text-sig-cyan text-[11px] font-semibold">#{d.id}</span>
              <span className="font-mono text-fg-2 text-[11px]">{fmtTime(d.edge_ts)}</span>
              <SeverityChip value={d.severity} size="sm" />
              <VariantChip value={d.variant} size="sm" />
              <CategoryChip value={d.category} />
              <span className="text-fg overflow-hidden text-ellipsis whitespace-nowrap">
                {d.defect_type}
                <span className="font-mono text-fg-3 ml-1.5 text-[10px]">&middot; {d.line_id}</span>
              </span>
              <span
                className="font-mono text-right tabular-nums text-[11px] font-medium"
                style={{ color: total > 2400 ? 'var(--color-sig-amber)' : 'var(--color-fg-1)' }}
              >
                {total}
              </span>
              <span
                className="font-mono text-right tabular-nums text-[11px]"
                style={{
                  color: d.vlm_metrics?.json_parse_ok ? 'var(--color-sig-green)' : 'var(--color-sig-red)',
                }}
              >
                {(d.confidence * 100).toFixed(1)}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function FilterGroup({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: [string, string][];
}) {
  return (
    <div className="flex items-center gap-1">
      <span className="font-mono text-[9px] text-fg-3 tracking-[0.14em] mr-1">{label}</span>
      {options.map(([v, l]) => (
        <button
          key={v}
          onClick={() => onChange(v)}
          className="font-mono text-[10px] px-2 py-0.5 cursor-pointer tracking-[0.08em]"
          style={{
            background: value === v ? 'var(--color-sig-cyan)' : 'transparent',
            color: value === v ? 'var(--color-bg-0)' : 'var(--color-fg-2)',
            border: `1px solid ${value === v ? 'var(--color-sig-cyan)' : 'var(--color-line)'}`,
            fontWeight: value === v ? 700 : 500,
          }}
        >
          {l}
        </button>
      ))}
    </div>
  );
}
