"use client";

import React from "react";
import type { DataSourceStatus } from "@/lib/data-source";
import { DataSourceBadge } from "./DataSourceBadge";

// ── Caveat items (bilingual: Chinese + English) ──────────────────────────────

const GATE_CAVEAT_ZH = "T2 EfficientAD 当前用于负载门控，不作为可靠缺陷检测器承诺。";
const GATE_CAVEAT_EN = "T2 EfficientAD is a load-shedding gate, not a reliable defect detector.";
const FASTSAM_CAVEAT_ZH = "FastSAM 仅输出 bbox 提案，未实现 mask decode。";
const FASTSAM_CAVEAT_EN = "FastSAM outputs bbox proposals only; mask decode is not implemented.";
const FOUR_B_CAVEAT_ZH = "4B 为扩展候选模型，不自动替代 2B 主线。";
const FOUR_B_CAVEAT_EN = "4B is an extension candidate; it does not replace the 2B mainline automatically.";
const SNAPSHOT_CAVEAT_ZH = "数据来自历史真实 RK3588 测试运行，非实时流。";
const SNAPSHOT_CAVEAT_EN = "Data is from a historical real RK3588 test run, not a live stream.";
const BBOX_CAVEAT_ZH = "bbox overlay 为 FastSAM/VLM 候选框，非可靠定位。纹理类（如 carpet）模型仅产生图像级异常信号。";
const BBOX_CAVEAT_EN = "BBox overlay is proposal-level (FastSAM/VLM), not verified localization. Texture categories produce image-level anomaly signal only.";
const PHASE10_CAVEAT_ZH = "Phase 10 使用 MVTec GT mask 训练的有监督定位器，非标准无监督 benchmark。";
const PHASE10_CAVEAT_EN = "Phase 10 localizer is supervised-trained from MVTec GT masks, not the standard unsupervised benchmark.";

// ── Page-level caveat banners ────────────────────────────────────────────────

interface CaveatBannerProps {
  dataSource: DataSourceStatus;
  caveats?: string[];
  style?: "profile" | "ab" | "overview" | "logs";
}

export function CaveatBanner({ dataSource, caveats, style = "overview" }: CaveatBannerProps) {
  const items: { zh: string; en: string }[] = [];

  if (style === "profile" || style === "overview") {
    items.push({ zh: GATE_CAVEAT_ZH, en: GATE_CAVEAT_EN });
    items.push({ zh: FASTSAM_CAVEAT_ZH, en: FASTSAM_CAVEAT_EN });
    items.push({ zh: BBOX_CAVEAT_ZH, en: BBOX_CAVEAT_EN });
    items.push({ zh: PHASE10_CAVEAT_ZH, en: PHASE10_CAVEAT_EN });
  }
  if (style === "ab") {
    items.push({ zh: GATE_CAVEAT_ZH, en: GATE_CAVEAT_EN });
    items.push({ zh: FASTSAM_CAVEAT_ZH, en: FASTSAM_CAVEAT_EN });
    items.push({ zh: BBOX_CAVEAT_ZH, en: BBOX_CAVEAT_EN });
    items.push({ zh: PHASE10_CAVEAT_ZH, en: PHASE10_CAVEAT_EN });
    items.push({ zh: FOUR_B_CAVEAT_ZH, en: FOUR_B_CAVEAT_EN });
  }
  if (dataSource.kind === "snapshot") {
    items.push({ zh: SNAPSHOT_CAVEAT_ZH, en: SNAPSHOT_CAVEAT_EN });
  }
  if (dataSource.kind === "mock") {
    items.push({
      zh: "后端不可达，使用 mock 数据。这不是真实流水线数据。",
      en: "Using mock data because backend is unreachable. This is NOT real pipeline data.",
    });
  }

  // Append manifest caveats if present — deduplicate by keyword overlap
  if (caveats?.length) {
    for (const c of caveats) {
      const cNorm = c.toLowerCase();
      const isDup = items.some(({ en }) => {
        const eNorm = en.toLowerCase();
        const cWords = new Set(cNorm.split(/\s+/).filter(w => w.length > 3));
        const eWords = new Set(eNorm.split(/\s+/).filter(w => w.length > 3));
        const shorter = cWords.size < eWords.size ? cWords : eWords;
        const longer = cWords.size < eWords.size ? eWords : cWords;
        let overlap = 0;
        for (const w of shorter) if (longer.has(w)) overlap++;
        return shorter.size > 0 && overlap / shorter.size > 0.3;
      });
      if (!isDup) items.push({ zh: c, en: c });
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
          Capability Caveats / 能力边界说明
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
            {item.zh}
            {item.en !== item.zh && (
              <span style={{ display: "block", fontSize: 10, color: "var(--fg-3)", marginLeft: 16 }}>
                {item.en}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Variant-specific caveat badges for AB Matrix cells ───────────────────────

export function VariantCaveatBadge({ variant }: { variant: string }) {
  let zh: string | null = null;
  let en: string | null = null;
  let color = "var(--fg-3)";

  if (variant === "2B_lora") {
    zh = "LoRA 在 PC bf16 下细粒度指标提升明显，但 RK3588 W8A8 下 defect_type_exact 坍塌。";
    en = "PC bf16 improves fine-grained metrics; RK3588 W8A8 collapses defect_type_exact.";
    color = "var(--acc)";
  } else if (variant === "4B_base" || variant === "4B_lora") {
    zh = "扩展候选模型；需修复 spatial merge 并回归验证 carpet 类。";
    en = "Extension candidate; requires spatial merge fix and carpet regression.";
    color = "#ff9f6c";
  }

  if (!zh) return null;

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
      {zh}
      {en !== zh && (
        <span style={{ display: "block", fontSize: 9, color: "var(--fg-3)", marginLeft: 16 }}>{en}</span>
      )}
    </div>
  );
}

// ── Snapshot vs live indicator for trace events ──────────────────────────────

export function TraceSourceNote({ source }: { source: "simulator" | "edge" | "snapshot" }) {
  const labels: Record<string, { zh: string; en: string; color: string }> = {
    simulator: { zh: "模拟器 trace 数据", en: "Simulator trace data", color: "var(--fg-3)" },
    edge: { zh: "真实 RK3588 trace", en: "Real RK3588 trace", color: "var(--ok)" },
    snapshot: { zh: "快照 trace（历史）", en: "Snapshot trace (historical)", color: "#7cdcff" },
  };
  const { zh, en, color } = labels[source] ?? labels.simulator;
  return (
    <span
      className="mono"
      style={{ fontSize: 9, color, letterSpacing: "0.08em", padding: "2px 6px", border: `1px solid ${color}`, background: `color-mix(in srgb, ${color} 10%, transparent)` }}
    >
      {zh} / {en}
    </span>
  );
}
