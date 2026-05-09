'use client';

import React, { useState, useEffect } from 'react';

// Panel — the fundamental V2 container
export function Panel({
  id,
  eyebrow,
  title,
  right,
  footer,
  children,
  padded = true,
  hot,
  className = '',
}: {
  id?: string;
  eyebrow?: string;
  title?: string;
  right?: React.ReactNode;
  footer?: React.ReactNode;
  children: React.ReactNode;
  padded?: boolean;
  hot?: string;
  className?: string;
}) {
  return (
    <section
      className={`bg-bg-1 border border-line flex flex-col ${className}`}
      style={hot ? { borderTopColor: hot } : undefined}
    >
      {(eyebrow || title || right) && (
        <header className="px-3.5 py-[9px] border-b border-line flex items-center justify-between gap-2.5 min-h-10 bg-bg-2">
          <div className="flex items-center gap-2.5 min-w-0">
            {id && (
              <>
                <span className="font-mono text-[10px] font-semibold text-sig-cyan">{id}</span>
                <span className="w-px h-3.5 bg-line" />
              </>
            )}
            {eyebrow && (
              <span className="font-mono text-[9px] font-medium tracking-[0.14em] uppercase text-fg-3">{eyebrow}</span>
            )}
            {title && (
              <span className="text-[13px] font-semibold text-fg">{title}</span>
            )}
          </div>
          {right && <div className="flex items-center gap-2">{right}</div>}
        </header>
      )}
      <div className={padded ? 'p-4 flex-1' : 'flex-1'}>{children}</div>
      {footer && (
        <footer className="px-3.5 py-2 border-t border-line bg-bg-2 font-mono text-[10px] text-fg-3 flex justify-between">
          {footer}
        </footer>
      )}
    </section>
  );
}

// MetricCell — KPI cell with flash animation
export function MetricCell({
  label,
  value,
  unit,
  sub,
  tone = 'default',
  flashKey,
}: {
  label: string;
  value: string | number;
  unit?: string;
  sub?: string;
  tone?: 'default' | 'cyan' | 'green' | 'amber' | 'red' | 'violet' | 'teal';
  flashKey?: number;
}) {
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    if (flashKey == null) return;
    setFlash(true);
    const t = setTimeout(() => setFlash(false), 600);
    return () => clearTimeout(t);
  }, [flashKey]);

  const colorMap: Record<string, string> = {
    default: 'var(--color-fg)',
    cyan: 'var(--color-sig-cyan)',
    green: 'var(--color-sig-green)',
    amber: 'var(--color-sig-amber)',
    red: 'var(--color-sig-red)',
    violet: 'var(--color-sig-violet)',
    teal: 'var(--color-sig-teal)',
  };
  const color = colorMap[tone] ?? 'var(--color-fg)';

  return (
    <div className="px-3.5 py-3 border-r border-line relative overflow-hidden bg-bg-1 min-h-[78px]">
      {flash && (
        <span
          className="absolute inset-0 pointer-events-none"
          style={{ background: color, animation: 'flash 0.6s forwards' }}
        />
      )}
      <div className="font-mono text-[9px] font-medium tracking-[0.14em] uppercase text-fg-3">{label}</div>
      <div className="flex items-baseline gap-1 mt-1.5">
        <span
          className="font-mono text-2xl font-medium leading-none tabular-nums"
          style={{ color, letterSpacing: '-0.01em' }}
        >
          {value}
        </span>
        {unit && <span className="font-mono text-[10px] text-fg-3">{unit}</span>}
      </div>
      {sub && <div className="font-mono text-[9px] text-fg-3 mt-1">{sub}</div>}
    </div>
  );
}

// StatusDot — online/stale/offline indicator
export function StatusDot({ state }: { state: 'online' | 'stale' | 'offline' }) {
  const m = {
    online: { c: 'var(--color-sig-green)', t: 'ONLINE', pulse: true },
    stale: { c: 'var(--color-sig-amber)', t: 'STALE', pulse: false },
    offline: { c: 'var(--color-sig-red)', t: 'OFFLINE', pulse: false },
  }[state] ?? { c: 'var(--color-sig-green)', t: 'ONLINE', pulse: true };

  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="relative w-2 h-2">
        <span
          className="absolute inset-0 rounded-full"
          style={{
            background: m.c,
            animation: m.pulse ? 'pulse-dot 1.4s infinite' : 'none',
            boxShadow: `0 0 6px ${m.c}`,
          }}
        />
      </span>
      <span
        className="font-mono text-[10px] font-semibold tracking-[0.16em]"
        style={{ color: m.c }}
      >
        {m.t}
      </span>
    </span>
  );
}

// SeverityChip — low/med/high badge
export function SeverityChip({ value, size = 'md' }: { value: string; size?: 'sm' | 'md' }) {
  const s = { low: 'var(--color-sev-low)', medium: 'var(--color-sev-med)', high: 'var(--color-sev-high)' }[value] ?? 'var(--color-sev-low)';
  const lbl = { low: 'LOW', medium: 'MED', high: 'HIGH' }[value] ?? value.toUpperCase();

  return (
    <span
      className="font-mono inline-flex items-center gap-1 font-semibold"
      style={{
        padding: size === 'sm' ? '0 5px' : '1px 6px',
        border: `1px solid ${s}`,
        color: s,
        background: `color-mix(in srgb, ${s} 14%, transparent)`,
        fontSize: size === 'sm' ? 9 : 10,
        letterSpacing: '0.14em',
      }}
    >
      <span className="w-1 h-1 rounded-full" style={{ background: s }} />
      {lbl}
    </span>
  );
}

// CategoryChip — MN/SCR/PIL code
export function CategoryChip({ value }: { value: string }) {
  const m: Record<string, { code: string; c: string }> = {
    metal_nut: { code: 'MN', c: 'var(--color-sig-cyan)' },
    screw: { code: 'SCR', c: 'var(--color-sig-mag)' },
    pill: { code: 'PIL', c: 'var(--color-sig-amber)' },
  };
  const { code, c } = m[value] ?? { code: '—', c: 'var(--color-fg-3)' };

  return (
    <span
      className="font-mono text-[9px] font-semibold tracking-[0.08em] px-1.5 py-px"
      style={{ border: `1px solid ${c}`, color: c }}
    >
      {code}
    </span>
  );
}

// VariantChip — A/B square badge
export function VariantChip({ value, size = 'md' }: { value: string; size?: 'sm' | 'md' }) {
  const c = value === 'A' ? 'var(--color-sig-violet)' : 'var(--color-sig-teal)';
  const dim = size === 'sm' ? 16 : 20;

  return (
    <span
      className="font-mono inline-flex items-center justify-center font-bold"
      style={{
        width: dim,
        height: dim,
        border: `1px solid ${c}`,
        color: c,
        background: `color-mix(in srgb, ${c} 16%, transparent)`,
        fontSize: size === 'sm' ? 9 : 10,
      }}
    >
      {value}
    </span>
  );
}

// INT8Badge — cyan border badge
export function INT8Badge() {
  return (
    <span
      className="font-mono text-[9px] font-bold text-sig-cyan border border-sig-cyan px-1 tracking-[0.06em]"
    >
      INT8
    </span>
  );
}

// NavMetric — top bar metric display
export function NavMetric({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="font-mono text-[9px] text-fg-3 tracking-[0.14em]">{label}</span>
      <span className="font-mono text-sm tabular-nums font-semibold" style={{ color }}>{value}</span>
    </div>
  );
}
