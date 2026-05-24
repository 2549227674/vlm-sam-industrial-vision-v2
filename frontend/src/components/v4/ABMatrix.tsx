"use client";

import React from "react";
import type { ActiveConfig } from "@/types/defect";
import type { AbMetrics, DashboardStatsLike } from "@/types/stats";
import type { DataSourceStatus } from "@/lib/data-source";
import { variantLabel, variantColor, fmtNumber } from "@/lib/mock-data";
import { CaveatBanner, VariantCaveatBadge } from "./CaveatBanner";

interface ABProps {
  stats: DashboardStatsLike;
  activeConfig: ActiveConfig;
  accent?: string;
  dataSource?: DataSourceStatus;
  manifestCaveats?: string[];
}

export function ABMatrix({ stats, activeConfig, dataSource, manifestCaveats }: ABProps) {
  const ab = stats.ab_compare;
  const active = `${activeConfig.model_size}_${activeConfig.variant}`;
  const totalN = Object.values(ab).reduce((s, x) => s + (x.count || 0), 0);

  const pctDrop = (a?: number, b?: number) => {
    if (!a || !b) return 0;
    return Math.round(((a - b) / a) * 100);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Decision cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
        <DecisionCard title="LoRA 效果" metric={`-${pctDrop(ab["2B_base"]?.avg_prompt_tokens, ab["2B_lora"]?.avg_prompt_tokens)}%`} metricLabel="提示词元" body="微调将提示词从约 1140 → 78 词元，JSON 解析率持平或更优，是单项 TTFT 收益最大的优化。" tint="var(--acc)" />
        <DecisionCard title="4B 质量权衡" metric={`${Math.round((ab["4B_lora"]?.avg_rss_mb || 0) / 1024 * 10) / 10} GB`} metricLabel="VLM 内存" body="4B 内存占用翻倍，TTFT 增加约 700ms，但 JSON 解析率和描述质量更高。" tint="#ff9f6c" />
        <DecisionCard title="部署决策" metric={variantLabel(active)} metricLabel="已部署" body="2B_lora 是产线延迟优先的默认选择；LPDDR 空余 ≥10 GB 时选用 4B_lora。" tint={variantColor(active)} />
      </div>

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        <div>
          <div className="eyebrow">变体矩阵 · 2×2</div>
          <h2 style={{ margin: "6px 0 0", fontSize: 24, fontWeight: 600, letterSpacing: "-0.02em" }}>
            Qwen3-VL <span style={{ color: "var(--fg-3)", fontWeight: 400 }}>2B / 4B</span>
            <span style={{ color: "var(--fg-3)", fontWeight: 400, margin: "0 6px" }}>×</span>
            <span style={{ color: "var(--fg-3)", fontWeight: 400 }}>Base / LoRA</span>
          </h2>
        </div>
        <span className="mono" style={{ fontSize: 11, color: "var(--fg-2)" }}>n = {fmtNumber(totalN)} · MVTec 测试集 70/30 划分</span>
      </div>

      {/* Matrix */}
      <div style={{ display: "grid", gridTemplateColumns: "120px 1fr 1fr", gridTemplateRows: "40px 1fr 1fr", gap: 1, background: "var(--line)", border: "1px solid var(--line)" }}>
        <div style={{ background: "var(--bg-2)" }} />
        <HeadCell label="基础提示词" sub="≈ 1140 tok" />
        <HeadCell label="LoRA 精简提示词" sub="≈ 78 tok · r=16 α=32" />
        <RowHead label="Qwen3-VL-2B" sub="约 5.0 GB · W8A8" />
        <Cell variant="2B_base" data={ab["2B_base"]} active={active} />
        <Cell variant="2B_lora" data={ab["2B_lora"]} active={active} winner />
        <RowHead label="Qwen3-VL-4B" sub="约 11.4 GB · W8A8" />
        <Cell variant="4B_base" data={ab["4B_base"]} active={active} />
        <Cell variant="4B_lora" data={ab["4B_lora"]} active={active} altWinner />
      </div>

      {/* Engineering decision footer */}
      <div style={{ padding: "14px 18px", background: "var(--bg-1)", border: "1px solid var(--line)", borderLeft: "3px solid var(--acc)", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
        <div>
          <div className="eyebrow" style={{ color: "var(--acc)" }}>工程决策</div>
          <div style={{ fontSize: 15, color: "var(--fg)", marginTop: 4, fontWeight: 500 }}>
            将 <span style={{ color: variantColor(active) }}>{variantLabel(active)}</span> 部署至产线摄像头。
            <span style={{ color: "var(--fg-2)", fontWeight: 400, marginLeft: 8 }}>相比基础版 TTFT 快约 2 倍，JSON 解析率提升 14 个百分点，内存占用 5 GB 以内。</span>
          </div>
        </div>
        <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>
          edge/config.yaml → vlm_model_size: <span style={{ color: "var(--fg-1)" }}>{activeConfig.model_size}</span> · vlm_variant: <span style={{ color: "var(--fg-1)" }}>{activeConfig.variant}</span>
        </span>
      </div>

      <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginTop: -8 }}>
        ↳ 旧版调用者使用 <span style={{ color: "var(--fg-2)" }}>variant=A/B</span> 将被映射至 <span style={{ color: "var(--fg-2)" }}>2B_base / 2B_lora</span> 以保持向后兼容。
      </div>

      {/* Data source caveat banner */}
      {dataSource && (
        <CaveatBanner dataSource={dataSource} caveats={manifestCaveats} style="ab" />
      )}
    </div>
  );
}

function DecisionCard({ title, metric, metricLabel, body, tint }: { title: string; metric: string; metricLabel: string; body: string; tint: string }) {
  return (
    <div style={{ background: "var(--bg-1)", border: "1px solid var(--line)", padding: 18, display: "flex", flexDirection: "column", gap: 8, borderTop: `2px solid ${tint}` }}>
      <div className="eyebrow" style={{ color: tint }}>{title}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
        <span className="mono" style={{ fontSize: 28, fontWeight: 500, color: "var(--fg)", letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums" }}>{metric}</span>
        <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>{metricLabel}</span>
      </div>
      <p style={{ margin: 0, fontSize: 12, color: "var(--fg-2)", lineHeight: 1.55 }}>{body}</p>
    </div>
  );
}

function HeadCell({ label, sub }: { label: string; sub: string }) {
  return (
    <div style={{ background: "var(--bg-2)", padding: "10px 14px", display: "flex", flexDirection: "column", justifyContent: "center" }}>
      <span style={{ fontSize: 13, color: "var(--fg)", fontWeight: 600 }}>{label}</span>
      <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.04em" }}>{sub}</span>
    </div>
  );
}

function RowHead({ label, sub }: { label: string; sub: string }) {
  return (
    <div style={{ background: "var(--bg-2)", padding: 14, display: "flex", flexDirection: "column", justifyContent: "center" }}>
      <span style={{ fontSize: 13, color: "var(--fg)", fontWeight: 600 }}>{label}</span>
      <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginTop: 2 }}>{sub}</span>
    </div>
  );
}

function Cell({ variant, data, active, winner, altWinner }: { variant: string; data: AbMetrics | undefined; active: string; winner?: boolean; altWinner?: boolean }) {
  const c = variantColor(variant);
  const isActive = variant === active;
  const d: AbMetrics = data || { count: 0, json_ok_rate: 0, avg_ttft_ms: 0, avg_decode_tps: 0, avg_rss_mb: 0, avg_prompt_tokens: 0, avg_output_tokens: 0 };

  return (
    <div style={{ background: "var(--bg-1)", padding: 18, position: "relative", borderLeft: isActive ? `3px solid ${c}` : "3px solid transparent", overflow: "hidden" }}>
      <div style={{ position: "absolute", right: -18, top: -28, fontFamily: "var(--font-sans)", fontSize: 110, fontWeight: 700, color: c, opacity: 0.05, lineHeight: 1, pointerEvents: "none", textTransform: "uppercase" }}>{variant.split("_")[0]}</div>
      <div style={{ position: "relative", display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ width: 14, height: 14, background: `color-mix(in srgb, ${c} 30%, transparent)`, border: `1px solid ${c}` }} />
            <div>
              <div className="mono" style={{ fontSize: 13, color: c, fontWeight: 700, letterSpacing: "0.04em" }}>{variant}</div>
              <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", marginTop: 1 }}>{variantLabel(variant)}</div>
            </div>
          </div>
          {winner && <span className="mono" style={{ fontSize: 9, padding: "3px 8px", border: "1px solid var(--acc)", color: "var(--acc)", background: "color-mix(in srgb, var(--acc) 14%, transparent)", letterSpacing: "0.16em", fontWeight: 700 }}>★ 已部署</span>}
          {altWinner && <span className="mono" style={{ fontSize: 9, padding: "3px 8px", border: "1px solid #ff9f6c", color: "#ff9f6c", background: "color-mix(in srgb, #ff9f6c 14%, transparent)", letterSpacing: "0.16em", fontWeight: 700 }}>质量替代</span>}
        </div>
        <VariantCaveatBadge variant={variant} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "var(--line)" }}>
          {[
            { l: "样本数", v: fmtNumber(d.count) },
            { l: "JSON 解析率", v: `${(d.json_ok_rate * 100).toFixed(1)}`, u: "%", c },
            { l: "首字延迟", v: Math.round(d.avg_ttft_ms), u: "ms", c },
            { l: "解码速率", v: d.avg_decode_tps.toFixed(2), u: "tok/s" },
            { l: "内存", v: fmtNumber(Math.round(d.avg_rss_mb)), u: "MB" },
            { l: "提示词元", v: Math.round(d.avg_prompt_tokens) },
            { l: "输出词元", v: Math.round(d.avg_output_tokens) },
          ].map((s) => (
            <div key={s.l} style={{ background: "var(--bg-1)", padding: "10px 12px" }}>
              <div className="eyebrow" style={{ fontSize: 9 }}>{s.l}</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 3, marginTop: 4 }}>
                <span className="mono" style={{ fontSize: 17, fontWeight: 500, color: s.c || "var(--fg)", letterSpacing: "-0.01em" }}>{s.v}</span>
                {s.u && <span className="mono" style={{ fontSize: 9, color: "var(--fg-3)" }}>{s.u}</span>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
