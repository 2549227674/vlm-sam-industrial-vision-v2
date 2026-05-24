"use client";

import React from "react";
import type { DataSourceStatus } from "@/lib/data-source";

interface DataSourceBadgeProps {
  status: DataSourceStatus;
  compact?: boolean;
}

const KIND_STYLES: Record<string, { bg: string; border: string; text: string; dotAnim: boolean }> = {
  live: {
    bg: "color-mix(in srgb, var(--ok) 14%, transparent)",
    border: "var(--ok)",
    text: "var(--ok)",
    dotAnim: true,
  },
  snapshot: {
    bg: "color-mix(in srgb, #7cdcff 14%, transparent)",
    border: "#7cdcff",
    text: "#7cdcff",
    dotAnim: false,
  },
  mock: {
    bg: "color-mix(in srgb, var(--warn) 18%, transparent)",
    border: "var(--warn)",
    text: "var(--warn)",
    dotAnim: false,
  },
  reconnecting: {
    bg: "color-mix(in srgb, var(--warn) 14%, transparent)",
    border: "var(--warn)",
    text: "var(--warn)",
    dotAnim: true,
  },
};

export function DataSourceBadge({ status, compact = false }: DataSourceBadgeProps) {
  const styles = KIND_STYLES[status.kind] ?? KIND_STYLES.mock;

  return (
    <span
      title={status.description}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: compact ? 4 : 6,
        padding: compact ? "2px 7px" : "4px 10px",
        border: `1px solid ${styles.border}`,
        background: styles.bg,
        borderRadius: compact ? 4 : 100,
        cursor: "help",
        whiteSpace: "nowrap",
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          background: styles.border,
          borderRadius: "50%",
          boxShadow: `0 0 5px ${styles.border}`,
          animation: styles.dotAnim ? "pulse-dot 1.4s infinite" : "none",
        }}
      />
      {status.kind === "mock" && (
        <span
          className="mono"
          style={{
            fontSize: 8,
            fontWeight: 800,
            letterSpacing: "0.16em",
            color: styles.text,
            textTransform: "uppercase",
            background: "color-mix(in srgb, var(--warn) 22%, transparent)",
            padding: "1px 4px",
          }}
        >
          MOCK
        </span>
      )}
      <span
        className="mono"
        style={{
          fontSize: compact ? 9 : 10,
          color: styles.text,
          fontWeight: 600,
          letterSpacing: "0.08em",
        }}
      >
        {status.label}
        {status.label !== status.labelEn && (
          <span style={{ opacity: 0.7, marginLeft: 4, fontSize: compact ? 8 : 9 }}>
            / {status.labelEn}
          </span>
        )}
      </span>
    </span>
  );
}

// ── Inline tooltip for defect_type ───────────────────────────────────────────

export function VlmDefectTooltip({ defectType }: { defectType: string }) {
  return (
    <span
      title="VLM 生成的结构化描述，不等同于板端精确 defect_type 分类。 / VLM-generated structured description. Not a guaranteed exact class on RK3588."
      style={{ cursor: "help", borderBottom: "1px dashed var(--fg-3)" }}
    >
      {defectType.replace(/_/g, " ")}
    </span>
  );
}
