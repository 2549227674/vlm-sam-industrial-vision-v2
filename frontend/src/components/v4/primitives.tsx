"use client";

import React, { useState, useCallback } from "react";
import { CATEGORY_LABEL, variantLabel, variantColor } from "@/lib/mock-data";
import { resolveImageUrl } from "@/lib/api";

// ── Severity chip ───────────────────────────────────────────────────────────

const SEV_COLOR: Record<string, string> = { low: "var(--ok)", medium: "var(--warn)", high: "var(--crit)" };
const SEV_LABEL: Record<string, string> = { low: "LOW", medium: "MED", high: "HIGH" };

export function SevPill({ value }: { value: string }) {
  const c = SEV_COLOR[value] || "var(--fg-3)";
  const l = SEV_LABEL[value] || value.toUpperCase();
  return (
    <span
      className="mono"
      style={{
        fontSize: 9, padding: "2px 7px", border: `1px solid ${c}`, color: c,
        letterSpacing: "0.12em", fontWeight: 700,
        background: `color-mix(in srgb, ${c} 14%, transparent)`,
      }}
    >
      {l}
    </span>
  );
}

// ── Category chip ───────────────────────────────────────────────────────────

export function CatPill({ value }: { value: string }) {
  const label = CATEGORY_LABEL[value] || value;
  return (
    <span
      className="mono"
      style={{
        fontSize: 9, padding: "2px 7px", border: "1px solid var(--line-hot)",
        color: "var(--fg-2)", letterSpacing: "0.08em", fontWeight: 600, textTransform: "uppercase",
        background: "var(--bg-2)",
      }}
    >
      {label}
    </span>
  );
}

// ── Variant chip ────────────────────────────────────────────────────────────

export function VariantPill({ value, compact }: { value: string; compact?: boolean }) {
  const c = variantColor(value);
  const label = compact ? value.split("_")[0] : variantLabel(value);
  return (
    <span
      className="mono"
      style={{
        fontSize: 9, padding: "2px 7px", border: `1px solid ${c}`, color: c,
        letterSpacing: "0.06em", fontWeight: 700,
        background: `color-mix(in srgb, ${c} 12%, transparent)`,
      }}
    >
      {label}
    </span>
  );
}

// ── Observation source chip ────────────────────────────────────────────────

const OBS_SOURCE_COLOR: Record<string, string> = {
  template: "var(--fg-3)",
  edge_vlm: "var(--acc)",
  cloud_vlm: "#7cdcff",
};
const OBS_SOURCE_LABEL: Record<string, string> = {
  template: "Template",
  edge_vlm: "Edge VLM",
  cloud_vlm: "Cloud VLM",
};

export function ObsSourcePill({ source }: { source: string }) {
  const c = OBS_SOURCE_COLOR[source] || "var(--fg-3)";
  const l = OBS_SOURCE_LABEL[source] || source;
  return (
    <span
      className="mono"
      style={{
        fontSize: 8, padding: "1px 6px", border: `1px solid ${c}`, color: c,
        letterSpacing: "0.1em", fontWeight: 600,
        background: `color-mix(in srgb, ${c} 12%, transparent)`,
      }}
    >
      {l}
    </span>
  );
}

// ── Metric tile ─────────────────────────────────────────────────────────────

export function KPITile({
  label, value, unit, sub, color = "var(--fg)",
}: {
  label: string; value: string | number; unit: string; sub: string; color?: string;
}) {
  return (
    <div style={{ background: "var(--bg-1)", padding: "14px 18px" }}>
      <div className="eyebrow">{label}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 5, marginTop: 6 }}>
        <span
          className="mono"
          style={{
            fontSize: 30, fontWeight: 500, color,
            letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums",
          }}
        >
          {value}
        </span>
        <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>{unit}</span>
      </div>
      <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginTop: 4 }}>{sub}</div>
    </div>
  );
}

// ── Section header ──────────────────────────────────────────────────────────

export function SectionHeader({
  number, title, caption,
}: {
  number: string; title: string; caption?: string;
}) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 18 }}>
      <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)", fontWeight: 500 }}>{number}</span>
      <div style={{ flex: 1 }}>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em" }}>{title}</h2>
        {caption && <p style={{ margin: "4px 0 0", color: "var(--fg-2)", fontSize: 13 }}>{caption}</p>}
      </div>
    </div>
  );
}

// ── Pipeline Gantt bar ──────────────────────────────────────────────────────

export function FrameGantt({ defect }: { defect: { pipeline_ms: { efficientad: number; fastsam?: number; qwen3vl?: number; localizer?: number; upload?: number; enrichment?: number } } }) {
  const pm = defect.pipeline_ms;
  // v1.3: show old chain (EAD/FastSAM/VLM) or new chain (EAD/Localizer/Upload) based on data
  const hasNewChain = (pm.localizer ?? 0) > 0 || (pm.upload ?? 0) > 0;
  const stages = hasNewChain
    ? [
        { k: "efficientad", color: "var(--core-0)", ms: pm.efficientad ?? 0, label: "EfficientAD" },
        { k: "localizer", color: "var(--core-1)", ms: pm.localizer ?? 0, label: "YOLO Localizer" },
        { k: "upload", color: "var(--core-2)", ms: pm.upload ?? 0, label: "Upload" },
      ]
    : [
        { k: "efficientad", color: "var(--core-0)", ms: pm.efficientad ?? 0, label: "EfficientAD" },
        { k: "fastsam", color: "var(--core-1)", ms: pm.fastsam ?? 0, label: "FastSAM" },
        { k: "qwen3vl", color: "var(--core-2)", ms: pm.qwen3vl ?? 0, label: "Qwen3-VL" },
      ];
  const total = stages.reduce((s, x) => s + x.ms, 0);
  return (
    <div>
      <div style={{ display: "flex", height: 8, border: "1px solid var(--line)", overflow: "hidden", background: "var(--bg-3)" }}>
        {stages.map(s => (
          <div key={s.k} title={`${s.label}: ${s.ms.toFixed(1)} ms`} style={{ width: total > 0 ? `${(s.ms / total) * 100}%` : "0%", background: s.color }} />
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", marginTop: 8, gap: 8 }}>
        {stages.map(s => (
          <div key={s.k} style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span style={{ width: 6, height: 6, background: s.color, borderRadius: "50%" }} />
            <span style={{ fontSize: 11, color: "var(--fg-2)" }}>{s.label}</span>
            <span className="mono" style={{ fontSize: 11, color: "var(--fg)", marginLeft: "auto" }}>
              {s.ms < 100 ? s.ms.toFixed(1) : Math.round(s.ms)}<span style={{ color: "var(--fg-3)" }}>ms</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Simulated sample placeholders (15 categories) ───────────────────────────

const _bg = "#0a0a10";

function NutSample() {
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <rect width="200" height="150" fill={_bg} />
      <polygon points="100,40 140,60 140,100 100,120 60,100 60,60" fill="#252530" stroke="#3a3a45" />
      <circle cx="100" cy="80" r="14" fill="#0a0a10" stroke="#3a3a45" />
    </svg>
  );
}

function ScrewSample() {
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <rect width="200" height="150" fill={_bg} />
      <ellipse cx="100" cy="40" rx="22" ry="6" fill="#2a2a35" stroke="#4a4a5a" strokeWidth="0.5" />
      <rect x="92" y="42" width="16" height="80" fill="#2a2a35" stroke="#4a4a5a" strokeWidth="0.5" />
      {Array.from({ length: 12 }).map((_, i) => (
        <line key={i} x1="92" y1={48 + i * 6} x2="108" y2={50 + i * 6} stroke="#5a5a6a" strokeWidth="0.4" />
      ))}
      <polygon points="92,122 108,122 100,134" fill="#3a3a48" />
    </svg>
  );
}

function PillSample() {
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <rect width="200" height="150" fill={_bg} />
      <rect x="55" y="65" width="90" height="28" rx="14" fill="#4a4a55" stroke="#5a5a6a" />
      <line x1="100" y1="65" x2="100" y2="93" stroke="#1a1a25" />
    </svg>
  );
}

function BottleSample() {
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <rect width="200" height="150" fill={_bg} />
      <circle cx="100" cy="80" r="48" fill="#1a2c3a" stroke="#2a4a5a" />
      <circle cx="100" cy="80" r="32" fill="#0a1a25" stroke="#1a3a4a" />
    </svg>
  );
}

function CapsuleSample() {
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <rect width="200" height="150" fill={_bg} />
      <rect x="50" y="62" width="100" height="34" rx="17" fill="#5a4a3a" stroke="#6a5a4a" />
      <rect x="50" y="62" width="50" height="34" rx="17" fill="#3a2a1a" />
    </svg>
  );
}

function CableSample() {
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <rect width="200" height="150" fill={_bg} />
      <circle cx="100" cy="75" r="42" fill="none" stroke="#3a3a45" strokeWidth="14" />
      <circle cx="100" cy="75" r="42" fill="none" stroke="#5a5a65" strokeWidth="2" strokeDasharray="4 6" />
    </svg>
  );
}

function ToothbrushSample() {
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <rect width="200" height="150" fill={_bg} />
      <rect x="60" y="68" width="80" height="14" fill="#2a2a35" />
      {Array.from({ length: 24 }).map((_, i) => (
        <line key={i} x1={62 + i * 3.3} y1="56" x2={62 + i * 3.3} y2="68" stroke="#5a5a6a" strokeWidth="0.6" />
      ))}
    </svg>
  );
}

function TransistorSample() {
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <rect width="200" height="150" fill={_bg} />
      <rect x="70" y="55" width="60" height="48" fill="#1a1a25" stroke="#3a3a48" />
      <line x1="80" y1="103" x2="80" y2="120" stroke="#6a6a75" />
      <line x1="100" y1="103" x2="100" y2="120" stroke="#6a6a75" />
      <line x1="120" y1="103" x2="120" y2="120" stroke="#6a6a75" />
    </svg>
  );
}

function ZipperSample() {
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <rect width="200" height="150" fill={_bg} />
      {Array.from({ length: 18 }).map((_, i) => (
        <g key={i}>
          <rect x="80" y={20 + i * 7} width="14" height="3" fill="#5a5a6a" />
          <rect x="106" y={23 + i * 7} width="14" height="3" fill="#5a5a6a" />
        </g>
      ))}
    </svg>
  );
}

function BlobSample({ tint = "#7a5536" }: { tint?: string }) {
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <rect width="200" height="150" fill={_bg} />
      <ellipse cx="100" cy="75" rx="42" ry="36" fill={tint} stroke="#4a3a2a" />
    </svg>
  );
}

function SurfaceSample({ tint = "#3a3a45", pattern = "grid" }: { tint?: string; pattern?: string }) {
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <rect width="200" height="150" fill={tint} />
      {pattern === "grid" && Array.from({ length: 20 }).map((_, i) => (
        <g key={i}>
          <line x1={i * 10} y1="0" x2={i * 10} y2="150" stroke="#000" strokeOpacity="0.25" />
          <line x1="0" y1={i * 10} x2="200" y2={i * 10} stroke="#000" strokeOpacity="0.25" />
        </g>
      ))}
      {pattern === "weave" && Array.from({ length: 16 }).map((_, i) => (
        <line key={i} x1="0" y1={i * 10 + 4} x2="200" y2={i * 10 + 4} stroke="#000" strokeOpacity="0.35" strokeWidth="2" />
      ))}
      {pattern === "wood" && Array.from({ length: 12 }).map((_, i) => (
        <path key={i} d={`M0,${i * 13} Q100,${i * 13 + 4} 200,${i * 13}`} fill="none" stroke="#000" strokeOpacity="0.3" strokeWidth="1.5" />
      ))}
      {pattern === "leather" && Array.from({ length: 40 }).map((_, i) => (
        <circle key={i} cx={(i * 17) % 200} cy={((i * 23) % 150)} r="2" fill="#000" fillOpacity="0.3" />
      ))}
      {pattern === "tile" && (
        <>
          <line x1="100" y1="0" x2="100" y2="150" stroke="#000" strokeOpacity="0.4" strokeWidth="2" />
          <line x1="0" y1="75" x2="200" y2="75" stroke="#000" strokeOpacity="0.4" strokeWidth="2" />
        </>
      )}
    </svg>
  );
}

const SAMPLE_MAP: Record<string, React.ReactNode> = {
  bottle: <BottleSample />,
  cable: <CableSample />,
  capsule: <CapsuleSample />,
  carpet: <SurfaceSample tint="#5b3a2a" pattern="weave" />,
  grid: <SurfaceSample tint="#3a3a3f" pattern="grid" />,
  hazelnut: <BlobSample tint="#7a5536" />,
  leather: <SurfaceSample tint="#3d2218" pattern="leather" />,
  metal_nut: <NutSample />,
  pill: <PillSample />,
  screw: <ScrewSample />,
  tile: <SurfaceSample tint="#4a4a55" pattern="tile" />,
  toothbrush: <ToothbrushSample />,
  transistor: <TransistorSample />,
  wood: <SurfaceSample tint="#5a3d22" pattern="wood" />,
  zipper: <ZipperSample />,
};

export function SimulatedSample({ category }: { category: string }) {
  return <>{SAMPLE_MAP[category] || <NutSample />}</>;
}

/** Real image with loading state and SimulatedSample fallback. */
export function RealImageWithFallback({
  imageUrl,
  category,
  showBadge = false,
  style: containerStyle,
}: {
  imageUrl: string;
  category: string;
  showBadge?: boolean;
  style?: React.CSSProperties;
}) {
  const resolved = resolveImageUrl(imageUrl);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(!resolved);

  const onLoad = useCallback(() => setLoaded(true), []);
  const onError = useCallback(() => setFailed(true), []);

  if (!resolved || failed) {
    return (
      <>
        <SimulatedSample category={category} />
        {showBadge && (
          <span style={{ position: "absolute", bottom: 4, right: 4, fontFamily: "var(--font-mono)", fontSize: 8, color: "var(--warn)", background: "rgba(0,0,0,0.6)", padding: "1px 5px", borderRadius: 2 }}>
            Placeholder
          </span>
        )}
      </>
    );
  }

  return (
    <>
      {!loaded && <SimulatedSample category={category} />}
      <img
        src={resolved}
        alt={`${category} defect`}
        onLoad={onLoad}
        onError={onError}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          objectFit: "cover",
          opacity: loaded ? 1 : 0,
          transition: "opacity 0.2s",
          ...containerStyle,
        }}
      />
      {showBadge && loaded && (
        <span style={{ position: "absolute", bottom: 4, right: 4, fontFamily: "var(--font-mono)", fontSize: 8, color: "var(--ok)", background: "rgba(0,0,0,0.6)", padding: "1px 5px", borderRadius: 2 }}>
          Real Image
        </span>
      )}
    </>
  );
}

// ── JSON highlighter ────────────────────────────────────────────────────────

export function highlightJson(line: string): string {
  return line
    .replace(/("(?:[^"\\]|\\.)*"):/g, '<span style="color: #7cdcff;">$1</span>:')
    .replace(/: ("(?:[^"\\]|\\.)*")/g, ': <span style="color: var(--acc);">$1</span>')
    .replace(/: (-?\d+\.?\d*)/g, ': <span style="color: var(--core-1);">$1</span>')
    .replace(/: (true|false|null)/g, ': <span style="color: #ff9f6c;">$1</span>');
}

// ── Enrichment status badge ──────────────────────────────────────────────

const ENRICH_STATUS_CONFIG: Record<string, { color: string; label: string; animate?: boolean }> = {
  pending:  { color: "var(--fg-3)", label: "PENDING",  animate: true },
  running:  { color: "var(--acc)",  label: "RUNNING",  animate: true },
  complete: { color: "var(--ok)",   label: "ENRICHED" },
  rejected: { color: "var(--warn)", label: "REJECTED" },
  failed:   { color: "var(--crit)", label: "FAILED" },
};

export function EnrichmentStatusBadge({ status, provider }: { status: string; provider?: string }) {
  const cfg = ENRICH_STATUS_CONFIG[status];
  if (!cfg) return null;

  const providerLabel = provider === "edge_vlm" ? "Edge VLM"
    : provider === "cloud_vlm" ? "Cloud VLM"
    : provider === "template" ? "Template"
    : null;

  return (
    <span
      className="mono"
      style={{
        fontSize: 9,
        padding: "2px 7px",
        border: `1px solid ${cfg.color}`,
        color: cfg.color,
        letterSpacing: "0.1em",
        fontWeight: 700,
        background: `color-mix(in srgb, ${cfg.color} 12%, transparent)`,
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
      }}
    >
      {cfg.animate && (
        <span
          style={{
            width: 5, height: 5, borderRadius: "50%",
            background: cfg.color,
            animation: "pulse-dot 1.4s infinite",
          }}
        />
      )}
      {cfg.label}
      {providerLabel && (
        <span style={{ opacity: 0.6, fontWeight: 400 }}>/ {providerLabel}</span>
      )}
    </span>
  );
}

export function EnrichmentInfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "120px 1fr", padding: "5px 12px" }}>
      <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>{label}</span>
      <span className="mono" style={{ fontSize: 10, color: "var(--fg-1)", wordBreak: "break-word" }}>{value}</span>
    </div>
  );
}
