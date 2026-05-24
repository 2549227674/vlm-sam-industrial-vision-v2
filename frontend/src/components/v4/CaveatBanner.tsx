"use client";

import React from "react";
import type { DataSourceStatus } from "@/lib/data-source";
import { DataSourceBadge } from "./DataSourceBadge";

// ── Caveat items ─────────────────────────────────────────────────────────────

const GATE_CAVEAT = "T2 EfficientAD is a load-shedding gate, not a reliable defect detector.";
const FASTSAM_CAVEAT = "FastSAM outputs bbox proposals only; mask decode is not implemented.";
const FOUR_B_CAVEAT = "4B is an extension candidate; it does not replace the 2B mainline automatically.";
const SNAPSHOT_CAVEAT = "Data is from a historical real RK3588 test run, not a live stream.";

// ── Page-level caveat banners ────────────────────────────────────────────────

interface CaveatBannerProps {
  dataSource: DataSourceStatus;
  caveats?: string[];
  style?: "profile" | "ab" | "overview" | "logs";
}

export function CaveatBanner({ dataSource, caveats, style = "overview" }: CaveatBannerProps) {
  const items: string[] = [];

  if (style === "profile" || style === "overview") {
    items.push(GATE_CAVEAT);
    items.push(FASTSAM_CAVEAT);
  }
  if (style === "ab") {
    items.push(GATE_CAVEAT);
    items.push(FASTSAM_CAVEAT);
    items.push(FOUR_B_CAVEAT);
  }
  if (dataSource.kind === "snapshot") {
    items.push(SNAPSHOT_CAVEAT);
  }
  if (dataSource.kind === "mock") {
    items.push("Using mock data because backend is unreachable. This is NOT real pipeline data.");
  }

  // Append manifest caveats if present — deduplicate by keyword overlap
  if (caveats?.length) {
    for (const c of caveats) {
      const cNorm = c.toLowerCase();
      const isDup = items.some(existing => {
        const eNorm = existing.toLowerCase();
        // Check if significant keywords overlap (>50% of shorter string's words)
        const cWords = new Set(cNorm.split(/\s+/).filter(w => w.length > 3));
        const eWords = new Set(eNorm.split(/\s+/).filter(w => w.length > 3));
        const shorter = cWords.size < eWords.size ? cWords : eWords;
        const longer = cWords.size < eWords.size ? eWords : cWords;
        let overlap = 0;
        for (const w of shorter) if (longer.has(w)) overlap++;
        return shorter.size > 0 && overlap / shorter.size > 0.3;
      });
      if (!isDup) items.push(c);
    }
  }

  if (!items.length) return null;

  const borderColor = dataSource.kind === "mock" ? "var(--warn)" : dataSource.kind === "snapshot" ? "#7cdcff" : "var(--line)";

  return (
    <div
      style={{
        padding: "10px 14px",
        background: dataSource.kind === "mock"
          ? "color-mix(in srgb, var(--warn) 8%, transparent)"
          : "var(--bg-1)",
        border: `1px solid ${borderColor}`,
        borderLeft: `3px solid ${borderColor}`,
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <span className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.12em", textTransform: "uppercase" }}>
          Capability Caveats
        </span>
        <DataSourceBadge status={dataSource} compact />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {items.map((item, i) => (
          <div
            key={i}
            style={{
              fontSize: 11,
              color: "var(--fg-2)",
              lineHeight: 1.55,
              paddingLeft: 10,
              borderLeft: "1px solid var(--line-soft)",
            }}
          >
            <span style={{ color: "var(--fg-3)", marginRight: 6 }}>&#x25B8;</span>
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Variant-specific caveat badges for AB Matrix cells ───────────────────────

export function VariantCaveatBadge({ variant }: { variant: string }) {
  let text: string | null = null;
  let color = "var(--fg-3)";

  if (variant === "2B_lora") {
    text = "PC bf16 improves fine-grained metrics; RK3588 W8A8 collapses defect_type_exact.";
    color = "var(--acc)";
  } else if (variant === "4B_base" || variant === "4B_lora") {
    text = "Extension candidate; requires spatial merge fix and carpet regression.";
    color = "#ff9f6c";
  }

  if (!text) return null;

  return (
    <div
      style={{
        marginTop: 8,
        padding: "6px 8px",
        background: `color-mix(in srgb, ${color} 8%, transparent)`,
        border: `1px solid color-mix(in srgb, ${color} 25%, transparent)`,
        borderLeft: `2px solid ${color}`,
        fontSize: 10,
        color: "var(--fg-2)",
        lineHeight: 1.5,
      }}
    >
      <span style={{ color, marginRight: 4, fontWeight: 700 }}>&#x26A0;</span>
      {text}
    </div>
  );
}

// ── Snapshot vs live indicator for trace events ──────────────────────────────

export function TraceSourceNote({ source }: { source: "simulator" | "edge" | "snapshot" }) {
  const labels: Record<string, { text: string; color: string }> = {
    simulator: { text: "Simulator trace data", color: "var(--fg-3)" },
    edge: { text: "Real RK3588 trace", color: "var(--ok)" },
    snapshot: { text: "Snapshot trace (historical)", color: "#7cdcff" },
  };
  const { text, color } = labels[source] ?? labels.simulator;
  return (
    <span
      className="mono"
      style={{ fontSize: 9, color, letterSpacing: "0.08em", padding: "2px 6px", border: `1px solid ${color}`, background: `color-mix(in srgb, ${color} 10%, transparent)` }}
    >
      {text}
    </span>
  );
}
