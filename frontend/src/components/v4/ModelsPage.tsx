"use client";

import React, { useState, useEffect, useMemo } from "react";
import type { ActiveConfig } from "@/types/defect";
import type { DataSourceStatus } from "@/lib/data-source";
import { variantColor } from "@/lib/mock-data";

interface ModelsProps {
  activeConfig: ActiveConfig;
  onChangeConfig: (c: ActiveConfig) => void;
  accent?: string;
  dataSource?: DataSourceStatus;
}

export function ModelsPage({ activeConfig, onChangeConfig, accent = "var(--acc)", dataSource }: ModelsProps) {
  const is4B = activeConfig.model_size === "4B";
  const variant_key = `${activeConfig.model_size}_${activeConfig.variant}`;
  const segments = [
    { label: "Linux + 驱动", gb: 1.4, color: "#5a5a6a" },
    { label: "EfficientAD-S", gb: 0.09, color: "var(--core-0)" },
    { label: "FastSAM-s", gb: 0.34, color: "var(--core-1)" },
    { label: "Qwen3-VL " + activeConfig.model_size, gb: is4B ? 8.7 : 3.1, color: "var(--core-2)" },
    { label: "C++ 缓冲", gb: 0.9, color: "#7d869c" },
    { label: "剩余空间", gb: is4B ? 4.57 : 10.17, color: "transparent", stripe: true },
  ];
  const total = segments.reduce((s, x) => s + x.gb, 0);
  const used = total - segments[segments.length - 1].gb;
  const ratio = used / 16;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
      {/* Hero */}
      <div style={{ paddingTop: 8 }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "4px 12px", border: "1px solid var(--line)", borderRadius: 100, marginBottom: 18 }}>
          <span style={{ width: 6, height: 6, background: accent, borderRadius: "50%", boxShadow: `0 0 6px ${accent}` }} />
          <span className="mono" style={{ fontSize: 10, color: "var(--fg-2)", letterSpacing: "0.1em" }}>模型 · 部署地图</span>
        </div>
        <h1 style={{ margin: 0, fontSize: 44, fontWeight: 600, lineHeight: 1.05, letterSpacing: "-0.025em" }}>
          三个模型共享 <span style={{ color: "var(--fg-3)" }}>同一块</span> RK3588，
          <span style={{ display: "block", color: "var(--fg-3)" }}><span style={{ color: accent }}>Qwen3-VL</span> 独占预算。</span>
        </h1>
        <p style={{ color: "var(--fg-2)", fontSize: 15, lineHeight: 1.65, marginTop: 16, maxWidth: 720 }}>
          每个 NPU 核承载一个模型。EfficientAD-S 和 FastSAM-s 体积小、速度快；VLM 主导延迟和内存，因此变体选择即是部署决策。
        </p>
      </div>

      {/* 3 NPU cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
        <NPUDeployCard core="NPU.0" coreColor="var(--core-0)" model="EfficientAD-S" task="异常检测" input="256×256" quant="INT8 · RKNN" latencyMs={4.8} latencyRange="3.0 – 6.1" outputs={["anomaly_score", "anomaly_map"]} memMb={86} />
        <NPUDeployCard core="NPU.1" coreColor="var(--core-1)" model="FastSAM-s" task="分割 / 边界框" input="640×640" quant="INT8 · RKNN" latencyMs={50} latencyRange="38 – 62" outputs={["masks", "bboxes"]} memMb={340} />
        <NPUDeployCard core="NPU.2" coreColor="var(--core-2)" model={`Qwen3-VL-${activeConfig.model_size}`} task={`VLM JSON · ${activeConfig.variant}`} input="448×448 + prompt" quant="W8A8 · RKLLM" latencyMs={is4B ? 3400 : 1800} latencyRange={is4B ? "3200 – 4100" : "1800 – 2700"} outputs={["structured JSON"]} memMb={is4B ? 8700 : 3100} variants="2B_base · 2B_lora · 4B_base · 4B_lora" bottleneck />
      </div>

      {/* Active config + memory budget */}
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.6fr)", gap: 14 }}>
        {/* Active config card */}
        <div style={{ background: "var(--bg-1)", border: "1px solid var(--line)", borderTop: `2px solid ${accent}`, padding: 18, display: "flex", flexDirection: "column", gap: 14 }}>
          <div>
            <div className="eyebrow" style={{ color: accent }}>当前配置</div>
            <div style={{ marginTop: 6, fontSize: 16, fontWeight: 600 }}>边缘 VLM 部署配置</div>
            <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginTop: 2 }}>edge/config.yaml · 启动时写入</div>
          </div>
          <div style={{ padding: "14px 16px", background: "var(--bg)", border: "1px solid var(--line-hot)", display: "flex", flexDirection: "column", gap: 4 }}>
            <span className="eyebrow" style={{ fontSize: 9 }}>变体键</span>
            <span className="mono" style={{ fontSize: 22, color: variantColor(variant_key), fontWeight: 700, letterSpacing: "-0.01em" }}>{variant_key}</span>
            <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>→ vlm_model_size: <span style={{ color: "var(--fg-1)" }}>{activeConfig.model_size}</span> · vlm_variant: <span style={{ color: "var(--fg-1)" }}>{activeConfig.variant}</span></span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <SegRow label="模型规模" value={activeConfig.model_size} onChange={v => onChangeConfig({ ...activeConfig, model_size: v as "2B" | "4B" })} options={[["2B", "2B · 低延迟"], ["4B", "4B · 高质量"]]} />
            <SegRow label="变体" value={activeConfig.variant} onChange={v => onChangeConfig({ ...activeConfig, variant: v as "base" | "lora" })} options={[["base", "base"], ["lora", "LoRA"]]} />
          </div>
          <div className="mono" style={{ fontSize: 11, color: "var(--fg-3)", lineHeight: 1.55, padding: "10px 12px", background: "var(--bg-2)", border: "1px solid var(--line-soft)", borderLeft: "2px solid var(--warn)" }}>
            max_context = 4096 · 禁止同时加载 2B 和 4B。
          </div>
        </div>

        {/* Memory budget */}
        <div style={{ background: "var(--bg-1)", border: "1px solid var(--line)", padding: 18, display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <div>
              <div className="eyebrow">LPDDR4 预算</div>
              <div style={{ marginTop: 4, fontSize: 16, fontWeight: 600 }}>
                <span style={{ color: variantColor(variant_key) }}>{used.toFixed(1)} GB</span>
                <span style={{ color: "var(--fg-3)", fontWeight: 400 }}> 已用 · 共 16.0 GB</span>
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div className="eyebrow">使用率</div>
              <div className="mono" style={{ fontSize: 22, color: ratio > 0.75 ? "var(--warn)" : "var(--fg)", fontWeight: 500, marginTop: 2 }}>{Math.round(ratio * 100)}%</div>
            </div>
          </div>
          <div style={{ display: "flex", height: 26, border: "1px solid var(--line)", background: "var(--bg-3)" }}>
            {segments.map((s, i) => (
              <div key={i} title={`${s.label} · ${s.gb.toFixed(2)} GB`} style={{ width: `${(s.gb / 16) * 100}%`, background: s.stripe ? "repeating-linear-gradient(45deg, transparent, transparent 4px, rgba(255,255,255,0.05) 4px, rgba(255,255,255,0.05) 8px)" : s.color, borderRight: i < segments.length - 1 ? "1px solid var(--bg)" : "none" }} />
            ))}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
            {segments.map((s, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 7 }}>
                <span style={{ width: 9, height: 9, background: s.stripe ? "transparent" : s.color, border: s.stripe ? "1px dashed var(--line-hot)" : "none" }} />
                <span style={{ fontSize: 11, color: "var(--fg-2)", flex: 1 }}>{s.label}</span>
                <span className="mono" style={{ fontSize: 10, color: "var(--fg)", fontVariantNumeric: "tabular-nums" }}>{s.gb.toFixed(2)}<span style={{ color: "var(--fg-3)" }}>GB</span></span>
              </div>
            ))}
          </div>
          <div className="mono" style={{ fontSize: 11, color: "var(--fg-3)", lineHeight: 1.55, padding: "10px 12px", background: "var(--bg-2)", border: "1px solid var(--line-soft)", borderLeft: `2px solid ${accent}` }}>
            {is4B ? "4B 适配但仅余约 4.6 GB——无并行批处理余量。仅在质量优先时使用。" : "2B 余约 10 GB，充足的余量用于采集、RGA 缓冲和 WebSocket 突发。"}
          </div>
        </div>
      </div>
    </div>
  );
}

function NPUDeployCard({ core, coreColor, model, task, input, quant, latencyMs, latencyRange, outputs, memMb, variants, bottleneck }: {
  core: string; coreColor: string; model: string; task: string; input: string; quant: string;
  latencyMs: number; latencyRange: string; outputs: string[]; memMb: number; variants?: string; bottleneck?: boolean;
}) {
  const data = useMemo(() => Array.from({ length: 24 }, () => 0.3 + Math.random() * 0.7), []);
  const [vals, setVals] = useState(data);
  useEffect(() => { const id = setInterval(() => { setVals(prev => { const next = prev.slice(1); next.push(0.3 + Math.random() * 0.7); return next; }); }, 1100); return () => clearInterval(id); }, []);

  const W = 220, H = 28;
  const max = Math.max(...vals), min = Math.min(...vals);
  const norm = vals.map(v => (v - min) / Math.max(0.0001, max - min));
  const pts = norm.map((v, i) => [i / (norm.length - 1) * W, H - 2 - v * (H - 4)]);
  const d = "M " + pts.map(p => p.join(",")).join(" L ");

  return (
    <div style={{ background: "var(--bg-1)", border: "1px solid var(--line)", padding: 18, display: "flex", flexDirection: "column", gap: 14, position: "relative", overflow: "hidden" }}>
      <span style={{ position: "absolute", top: 0, left: 0, width: 10, height: 10, background: coreColor }} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div className="mono" style={{ fontSize: 10, color: coreColor, letterSpacing: "0.14em", fontWeight: 700 }}>{core}</div>
          <div style={{ fontSize: 19, fontWeight: 600, marginTop: 4, letterSpacing: "-0.015em", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{model}</div>
          <div className="mono" style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 2 }}>{task}</div>
        </div>
        {bottleneck && <span className="mono" style={{ fontSize: 9, padding: "3px 7px", background: "color-mix(in srgb, var(--core-2) 18%, transparent)", color: "var(--core-2)", letterSpacing: "0.12em", fontWeight: 700 }}>瓶颈</span>}
      </div>
      <div>
        <div className="eyebrow">P50 延迟</div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 5, marginTop: 4 }}>
          <span className="mono" style={{ fontSize: 32, fontWeight: 500, color: coreColor, letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums" }}>{latencyMs < 100 ? latencyMs.toFixed(1) : Math.round(latencyMs)}</span>
          <span className="mono" style={{ fontSize: 12, color: "var(--fg-3)" }}>ms</span>
          <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginLeft: 8 }}>范围 {latencyRange} ms</span>
        </div>
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: "100%", height: 28, marginTop: 6, display: "block" }}>
          <path d={d} fill="none" stroke={coreColor} strokeWidth="1.4" style={{ filter: `drop-shadow(0 0 3px ${coreColor})` }} />
          <path d={d + ` L ${W},${H} L 0,${H} Z`} fill={coreColor} opacity="0.08" />
        </svg>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 4 }}>
        {[
          ["输入", input], ["量化", quant], ["输出", outputs.join(", ")],
          ["内存", memMb < 1024 ? `${memMb} MB` : `${(memMb / 1024).toFixed(1)} GB`],
          ...(variants ? [["变体", variants] as [string, string]] : []),
        ].map(([k, v]) => (
          <div key={k} style={{ display: "flex", justifyContent: "space-between", gap: 8, fontFamily: "var(--font-mono)", fontSize: 11, borderBottom: "1px dashed var(--line-soft)", paddingBottom: 4 }}>
            <span style={{ color: "var(--fg-3)", letterSpacing: "0.06em" }}>{k}</span>
            <span style={{ color: "var(--fg-1)", textAlign: "right" }}>{v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SegRow({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <div>
      <div className="eyebrow" style={{ marginBottom: 4 }}>{label}</div>
      <div style={{ display: "flex", border: "1px solid var(--line)" }}>
        {options.map(([v, l], i) => {
          const active = value === v;
          return (
            <button key={v} onClick={() => onChange(v)} style={{
              flex: 1, padding: "8px 10px", fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: "0.06em",
              fontWeight: 600, background: active ? "var(--acc)" : "transparent",
              color: active ? "var(--bg)" : "var(--fg-2)", border: "none",
              borderRight: i < options.length - 1 ? "1px solid var(--line)" : "none", cursor: "pointer",
            }}>{l}</button>
          );
        })}
      </div>
    </div>
  );
}
