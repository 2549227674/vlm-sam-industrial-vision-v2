"use client";

import React, { useState, useEffect, useMemo, useRef, useCallback } from "react";
import type { DefectRead } from "@/types/defect";
import { CATEGORY_LABEL, variantColor, variantIsLora } from "@/lib/mock-data";

// ── Chrome Trace export ─────────────────────────────────────────────────────

const THREAD_NAMES: [string, string][] = [
  ["T1.capture", "T1 · capture"], ["T2.pipeline", "T2 · pipeline"],
  ["T3.vlm", "T3 · VLM worker"], ["T4.upload", "T4 · upload"],
  ["NPU.core0", "NPU.0 · EfficientAD-S"], ["NPU.core1", "NPU.1 · FastSAM-s"], ["NPU.core2", "NPU.2 · Qwen3-VL"],
  ["CPU.A76_0", "A76.0"], ["CPU.A76_1", "A76.1"], ["CPU.A76_2", "A76.2"], ["CPU.A76_3", "A76.3"],
  ["CPU.A55_0", "A55.0"], ["CPU.A55_1", "A55.1"], ["CPU.A55_2", "A55.2"], ["CPU.A55_3", "A55.3"],
];

function toChromeTrace(defect: DefectRead) {
  const pid = 1;
  const metadataEvents = [
    { name: "process_name", ph: "M" as const, pid, tid: 0, args: { name: `RK3588 Edge Pipeline · frame #${defect.id}` } },
    ...THREAD_NAMES.map(([tid, name]) => ({ name: "thread_name", ph: "M" as const, pid, tid, args: { name } })),
  ];
  const traceEvents = (defect.trace_events ?? []).map(e => ({
    name: e.name, cat: e.cat ?? "default", ph: e.ph ?? "X", ts: e.ts, dur: e.dur, pid, tid: e.tid,
    args: { frame_id: defect.id, line_id: defect.line_id, category: defect.category, defect_type: defect.defect_type, severity: defect.severity, variant: defect.variant, confidence: defect.confidence, anomaly_score: defect.anomaly_score },
  }));
  return { traceEvents: [...metadataEvents, ...traceEvents], displayTimeUnit: "ms" as const };
}
import { VariantPill, SimulatedSample } from "./primitives";

const LANE_GROUPS = [
  { label: "SOFTWARE THREADS", tids: ["T1.capture", "T2.pipeline", "T3.vlm", "T4.upload"] },
  { label: "NPU HARDWARE", tids: ["NPU.core0", "NPU.core1", "NPU.core2"] },
  { label: "ARM CORES", tids: ["CPU.A76_0", "CPU.A76_1", "CPU.A76_2", "CPU.A76_3", "CPU.A55_0", "CPU.A55_1", "CPU.A55_2", "CPU.A55_3"] },
];
const LANE_LABELS: Record<string, { name: string; hint: string }> = {
  "T1.capture": { name: "T1 · capture", hint: "V4L2 dequeue" }, "T2.pipeline": { name: "T2 · pipeline", hint: "RGA + EAD + FastSAM" },
  "T3.vlm": { name: "T3 · vlm", hint: "Qwen3-VL prompt + decode" }, "T4.upload": { name: "T4 · upload", hint: "libcurl POST" },
  "NPU.core0": { name: "NPU.0", hint: "EfficientAD-S [INT8]" }, "NPU.core1": { name: "NPU.1", hint: "FastSAM-s [INT8]" },
  "NPU.core2": { name: "NPU.2", hint: "Qwen3-VL [W8A8]" },
  "CPU.A76_0": { name: "A76.0", hint: "2.4 GHz" }, "CPU.A76_1": { name: "A76.1", hint: "2.4 GHz" },
  "CPU.A76_2": { name: "A76.2", hint: "2.4 GHz" }, "CPU.A76_3": { name: "A76.3", hint: "2.4 GHz" },
  "CPU.A55_0": { name: "A55.0", hint: "1.8 GHz · eff" }, "CPU.A55_1": { name: "A55.1", hint: "1.8 GHz · eff" },
  "CPU.A55_2": { name: "A55.2", hint: "1.8 GHz · eff" }, "CPU.A55_3": { name: "A55.3", hint: "1.8 GHz · eff" },
};
const CAT_COLOR: Record<string, string> = {
  io: "#7cdcff", mem: "#7d869c", rga: "#ffbf5c", infer: "var(--acc)", npu: "var(--acc)", cpu: "#b07cff", sync: "#555d72",
  "vlm-prompt": "#ff7a90", "vlm-decode": "#ff5c7a", "vlm-encode": "#f472b6",
};

export function ProfilePage({ defects, accent = "var(--acc)", initialFrameIdx = 0 }: { defects: DefectRead[]; accent?: string; initialFrameIdx?: number }) {
  const [frameIdx, setFrameIdx] = useState(initialFrameIdx);
  const [pinnedId, setPinnedId] = useState<number | null>(null);
  useEffect(() => { setFrameIdx(initialFrameIdx); }, [initialFrameIdx]);
  useEffect(() => {
    if (defects.length > 0 && pinnedId === null) {
      setPinnedId(defects[initialFrameIdx]?.id ?? defects[0].id);
    }
  }, [defects, initialFrameIdx, pinnedId]);
  const resolvedIdx = useMemo(() => {
    if (pinnedId === null) return 0;
    const idx = defects.findIndex(d => d.id === pinnedId);
    return idx >= 0 ? idx : 0;
  }, [defects, pinnedId]);
  const [zoom, setZoom] = useState({ start_us: 0, end_us: 0 });
  const [hover, setHover] = useState<{ x: number; y: number; event: { name: string; ts: number; dur: number; cat?: string }; laneName: string } | null>(null);
  const [showCritical, setShowCritical] = useState(true);

  const defect = defects[resolvedIdx];
  const span = useMemo(() => {
    if (!defect?.trace_events?.length) return { start: 0, end: 1000 };
    let min = Infinity, max = -Infinity;
    for (const e of defect.trace_events) { if (e.ts < min) min = e.ts; if (e.ts + e.dur > max) max = e.ts + e.dur; }
    return { start: min, end: max };
  }, [defect]);
  const visible = zoom.start_us === 0 && zoom.end_us === 0 ? span : { start: zoom.start_us, end: zoom.end_us };
  const totalDur = visible.end - visible.start;

  const byTid = useMemo(() => {
    const m: Record<string, { name: string; ts: number; dur: number; tid: string; ph: "X"; cat?: string }[]> = {};
    if (defect?.trace_events) for (const e of defect.trace_events) { (m[e.tid] = m[e.tid] || []).push(e); }
    return m;
  }, [defect]);

  if (!defect) return <div style={{ background: "var(--bg-1)", border: "1px solid var(--line)", padding: 60, textAlign: "center", color: "var(--fg-3)" }}><span className="mono" style={{ fontSize: 14 }}>暂无追踪事件。</span></div>;

  const total_us = defect.trace_events ? Math.max(...defect.trace_events.map(e => e.ts + e.dur)) : 0;
  const npu2 = (byTid["NPU.core2"] || []).reduce((s, e) => s + e.dur, 0);
  const npu0 = (byTid["NPU.core0"] || []).reduce((s, e) => s + e.dur, 0);
  const npu1 = (byTid["NPU.core1"] || []).reduce((s, e) => s + e.dur, 0);
  const npuTotal = npu0 + npu1 + npu2;
  const prompt = defect.trace_events?.filter(e => e.cat === "vlm-prompt" && e.tid === "NPU.core2").reduce((s, e) => s + e.dur, 0) || 0;
  const decode = defect.trace_events?.filter(e => e.cat === "vlm-decode" && e.tid === "NPU.core2").reduce((s, e) => s + e.dur, 0) || 0;
  const upload = (byTid["T4.upload"] || []).reduce((s, e) => s + e.dur, 0);
  const npu2Share = npuTotal > 0 ? npu2 / npuTotal : 0;
  const promptShare = prompt + decode > 0 ? prompt / (prompt + decode) : 0;

  const legend = [["NPU 推理", "infer"], ["VLM 提示", "vlm-prompt"], ["VLM 解码", "vlm-decode"], ["CPU", "cpu"], ["IO", "io"], ["RGA", "rga"], ["同步", "sync"]] as const;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      {/* Filmstrip */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
          <span className="eyebrow">帧胶片 · 点击切换</span>
          <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>最近 {Math.min(14, defects.length)} 帧</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${Math.min(14, defects.length)}, 1fr)`, gap: 4 }}>
          {defects.slice(0, 14).map((d, i) => {
            const totalMs = Math.round(d.pipeline_ms.efficientad + d.pipeline_ms.fastsam + d.pipeline_ms.qwen3vl);
            const sevColor = { low: "var(--ok)", medium: "var(--warn)", high: "var(--crit)" }[d.severity];
            const active = i === resolvedIdx;
            return (
              <button key={d.id} onClick={() => { setFrameIdx(i); setPinnedId(d.id); }} style={{
                padding: 0, background: "var(--bg-1)", border: active ? "2px solid var(--acc)" : "1px solid var(--line)",
                cursor: "pointer", position: "relative", overflow: "hidden", boxShadow: active ? "0 0 12px var(--acc-glow)" : "none",
              }}>
                <div style={{ position: "relative", width: "100%", aspectRatio: "16/10", overflow: "hidden" }}>
                  <SimulatedSample category={d.category} />
                  <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
                    {d.bboxes.slice(0, 1).map((b, j) => (
                      <rect key={j} x={b.x * 100} y={b.y * 100} width={b.w * 100} height={b.h * 100} fill="none" stroke={sevColor} strokeWidth="0.4" vectorEffect="non-scaling-stroke" />
                    ))}
                  </svg>
                  <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: sevColor }} />
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "3px 6px", fontFamily: "var(--font-mono)", fontSize: 8.5, color: "var(--fg-2)", borderTop: "1px solid var(--line)", background: active ? "var(--bg-2)" : "var(--bg-1)" }}>
                  <span style={{ color: active ? "var(--fg)" : "var(--fg-3)" }}>#{d.id}</span>
                  <span style={{ color: totalMs > 2800 ? "var(--warn)" : "var(--fg-3)" }}>{totalMs}ms</span>
                </div>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 8, padding: "0 6px 3px", color: variantColor(d.variant), background: active ? "var(--bg-2)" : "var(--bg-1)", textAlign: "left" }}>{d.variant}</div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Bottleneck summary */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 1, background: "var(--line)", border: "1px solid var(--line)" }}>
        {[
          { l: "关键路径", v: (npuTotal / 1000).toFixed(1), u: "ms", sub: "NPU 串行累积", c: accent, big: true },
          { l: "NPU.2 占比", v: `${Math.round(npu2Share * 100)}`, u: "%", sub: `${(npu2 / 1000).toFixed(1)} ms / ${(npuTotal / 1000).toFixed(1)} ms`, c: "var(--core-2)", big: true },
          { l: "提示 vs 解码", v: `${Math.round(promptShare * 100)}/${Math.round((1 - promptShare) * 100)}`, u: "%", sub: `${(prompt / 1000).toFixed(0)} ms prompt · ${(decode / 1000).toFixed(0)} ms decode`, c: "var(--fg)" },
          { l: "上传开销", v: (upload / 1000).toFixed(0), u: "ms", sub: `${total_us > 0 ? ((upload / total_us) * 100).toFixed(1) : 0}% of E2E`, c: "var(--fg)" },
        ].map((s) => (
          <div key={s.l} style={{ background: "var(--bg-1)", padding: "14px 16px" }}>
            <div className="eyebrow" style={{ fontSize: 9 }}>{s.l}</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginTop: 6 }}>
              <span className="mono" style={{ fontSize: s.big ? 28 : 22, fontWeight: 500, color: s.c, letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums" }}>{s.v}</span>
              {s.u && <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>{s.u}</span>}
            </div>
            <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginTop: 3 }}>{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Trace viewer header */}
      <div style={{ background: "var(--bg-1)", border: "1px solid var(--line)", padding: "16px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 18, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 22, flexWrap: "wrap" }}>
          <div>
            <div className="eyebrow">当前帧</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 4 }}>
              <span className="mono" style={{ fontSize: 22, color: "var(--fg)", fontWeight: 500 }}>#{defect.id}</span>
              <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>· {defect.line_id} · {CATEGORY_LABEL[defect.category] || defect.category}</span>
            </div>
          </div>
          <span style={{ width: 1, height: 36, background: "var(--line)" }} />
          <div>
            <div className="eyebrow">端到端延迟</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginTop: 4 }}>
              <span className="mono" style={{ fontSize: 22, color: accent, fontWeight: 500 }}>{(total_us / 1000).toFixed(1)}</span>
              <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>ms</span>
            </div>
          </div>
          <span style={{ width: 1, height: 36, background: "var(--line)" }} />
          <div><div className="eyebrow">VARIANT</div><div style={{ marginTop: 4 }}><VariantPill value={defect.variant} /></div></div>
          <span style={{ width: 1, height: 36, background: "var(--line)" }} />
          <div><div className="eyebrow">事件数</div><span className="mono" style={{ fontSize: 16, color: "var(--fg-1)", marginTop: 4, display: "inline-block" }}>{defect.trace_events?.length ?? 0}</span></div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button onClick={() => { const ni = Math.min(defects.length - 1, resolvedIdx + 1); setFrameIdx(ni); setPinnedId(defects[ni].id); }} disabled={resolvedIdx >= defects.length - 1} style={{ background: "transparent", color: resolvedIdx >= defects.length - 1 ? "var(--fg-4)" : "var(--fg-2)", border: "1px solid var(--line)", padding: "4px 10px", fontSize: 11, fontFamily: "var(--font-mono)", cursor: resolvedIdx >= defects.length - 1 ? "default" : "pointer" }}>‹ 更早</button>
          <span className="mono" style={{ fontSize: 11, color: "var(--fg-2)", padding: "0 4px" }}>{resolvedIdx + 1} / {defects.length}</span>
          <button onClick={() => { const ni = Math.max(0, resolvedIdx - 1); setFrameIdx(ni); setPinnedId(defects[ni].id); }} disabled={resolvedIdx === 0} style={{ background: "transparent", color: resolvedIdx === 0 ? "var(--fg-4)" : "var(--fg-2)", border: "1px solid var(--line)", padding: "4px 10px", fontSize: 11, fontFamily: "var(--font-mono)", cursor: resolvedIdx === 0 ? "default" : "pointer" }}>更新 ›</button>
          <button onClick={() => setZoom({ start_us: 0, end_us: 0 })} style={{ background: "transparent", color: "var(--fg-2)", border: "1px solid var(--line)", padding: "4px 10px", fontSize: 11, fontFamily: "var(--font-mono)", cursor: "pointer" }}>重置缩放</button>
          <span style={{ width: 1, height: 20, background: "var(--line)", margin: "0 2px" }} />
          <button onClick={() => setShowCritical(c => !c)} style={{ background: showCritical ? "var(--bg-3)" : "transparent", color: showCritical ? "var(--fg)" : "var(--fg-2)", border: `1px solid ${showCritical ? "var(--fg-2)" : "var(--line)"}`, padding: "4px 10px", fontSize: 11, fontFamily: "var(--font-mono)", cursor: "pointer", letterSpacing: "0.04em" }}>关键路径</button>
          <button onClick={() => { try { navigator.clipboard.writeText(JSON.stringify(toChromeTrace(defect), null, 2)); } catch {} }} style={{ background: "transparent", color: "var(--fg-2)", border: "1px solid var(--line)", padding: "4px 10px", fontSize: 11, fontFamily: "var(--font-mono)", cursor: "pointer" }}>复制追踪</button>
          <button onClick={() => { const trace = toChromeTrace(defect); const blob = new Blob([JSON.stringify(trace, null, 2)], { type: "application/json" }); const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = `trace_${defect.id}.json`; a.click(); URL.revokeObjectURL(url); }} style={{ background: "transparent", color: "var(--fg-2)", border: "1px solid var(--line)", padding: "4px 10px", fontSize: 11, fontFamily: "var(--font-mono)", cursor: "pointer" }}>↓ 导出</button>
        </div>
      </div>

      {/* Trace viewer + explanation */}
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 320px", gap: 14 }}>
        {/* Trace SVG */}
        <div style={{ position: "relative", background: "var(--bg-1)", border: "1px solid var(--line)", overflow: "visible" }}>
          <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--line)", background: "var(--bg-2)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span className="eyebrow">CHROME 追踪 · 滚轮缩放 · 拖拽平移 · 双击重置</span>
            <div style={{ display: "flex", gap: 10 }}>
              {legend.map(([l, k]) => (
                <span key={k} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                  <span style={{ width: 9, height: 9, background: CAT_COLOR[k] }} />
                  <span className="mono" style={{ fontSize: 9, color: "var(--fg-2)" }}>{l}</span>
                </span>
              ))}
            </div>
          </div>
          <div onMouseLeave={() => { setPinnedId(null); }}>
            <TraceCanvas defect={defect} byTid={byTid} span={span} visible={visible} totalDur={totalDur} onZoom={(s, e) => setZoom({ start_us: s, end_us: e })} onHover={setHover} hover={hover} showCritical={showCritical} accent={accent} onSvgLeave={() => { setPinnedId(null); }} />
          </div>
        </div>

        {/* Bottleneck explanation */}
        <div style={{ background: "var(--bg-1)", border: "1px solid var(--line)", padding: 18, display: "flex", flexDirection: "column", gap: 14, borderTop: `2px solid ${accent}` }}>
          <div>
            <div className="eyebrow" style={{ color: accent }}>为什么这帧慢</div>
            <h3 style={{ margin: "6px 0 0", fontSize: 16, fontWeight: 600, lineHeight: 1.4 }}>
              Qwen3-VL 在 NPU.2 上占据关键路径的 <span style={{ color: "var(--core-2)" }}>{Math.round(npu2Share * 100)}%</span>。
            </h3>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {[
              npu2Share > 0.9 ? "NPU.2 完全串行——Qwen3-VL 主导关键路径。" : null,
              promptShare > 0.5 && !variantIsLora(defect.variant) ? "提示词主导解码——切换至 *_lora 变体可将提示词缩短 14 倍。" : null,
              promptShare > 0.5 ? "提示词仍占 VLM 的约一半，建议检查分词器/对话模板开销。" : null,
              "EfficientAD-S + FastSAM-s 合计不足 E2E 的 5%，无需优化。",
            ].filter(Boolean).map((t, i) => (
              <div key={i} style={{ padding: "8px 10px", background: "var(--bg-2)", border: "1px solid var(--line-soft)", borderLeft: `2px solid ${accent}`, fontSize: 12, color: "var(--fg-1)", lineHeight: 1.5 }}>
                <span style={{ color: accent, marginRight: 6 }}>▸</span>{t}
              </div>
            ))}
          </div>
          <div style={{ marginTop: 4, padding: "10px 12px", background: "var(--bg-2)", border: "1px solid var(--line-soft)" }}>
            <div className="eyebrow" style={{ marginBottom: 6 }}>导出</div>
            <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", lineHeight: 1.6 }}>
              → 复制追踪 JSON 到剪贴板<br />→ Download <span style={{ color: "var(--fg-1)" }}>trace_{defect.id}.json</span><br />→ 拖入 <span style={{ color: "var(--fg-1)" }}>chrome://tracing</span> 或 <span style={{ color: "var(--fg-1)" }}>perfetto.dev</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── HoverTip ─────────────────────────────────────────────────────────────────

type HoverState = { x: number; y: number; event: { name: string; ts: number; dur: number; cat?: string }; laneName: string };

function HoverTip({ hover, containerWidth }: { hover: HoverState; containerWidth: number }) {
  const tipRef = useRef<HTMLDivElement>(null);
  const [adjustedLeft, setAdjustedLeft] = useState(hover.x);

  useEffect(() => {
    if (!tipRef.current) return;
    const tipW = tipRef.current.offsetWidth;
    const half = tipW / 2;
    const clamped = Math.min(containerWidth - half - 8, Math.max(140 + half, hover.x));
    setAdjustedLeft(clamped);
  }, [hover.x, containerWidth]);

  return (
    <div
      ref={tipRef}
      style={{
        position: "absolute",
        left: adjustedLeft,
        top: hover.y,
        transform: "translate(-50%, calc(-100% - 10px))",
        pointerEvents: "none",
        zIndex: 20,
        background: "var(--bg-1)",
        border: "1px solid var(--line-hot)",
        padding: "8px 10px",
        fontSize: 11,
        lineHeight: 1.5,
        minWidth: 180,
        maxWidth: 280,
        boxShadow: "0 4px 16px rgba(0,0,0,0.55)",
        animation: "fadeIn 80ms ease-out",
      }}
    >
      <div className="mono" style={{ color: "var(--fg)", fontWeight: 600, fontSize: 12 }}>{hover.event.name}</div>
      <div className="mono" style={{ color: "var(--fg-3)", fontSize: 9, marginTop: 2 }}>{hover.laneName}</div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, gap: 12 }}>
        <span style={{ color: "var(--fg-3)" }}>ts</span>
        <span className="mono" style={{ color: "var(--fg-1)" }}>{(hover.event.ts / 1000).toFixed(2)}<span style={{ color: "var(--fg-3)" }}>ms</span></span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 2 }}>
        <span style={{ color: "var(--fg-3)" }}>dur</span>
        <span className="mono" style={{ color: CAT_COLOR[hover.event.cat || ""] || "var(--fg-1)", fontWeight: 600 }}>{(hover.event.dur / 1000).toFixed(2)}<span style={{ color: "var(--fg-3)" }}>ms</span></span>
      </div>
    </div>
  );
}

// ── Trace SVG canvas ────────────────────────────────────────────────────────

function TraceCanvas({ byTid, span, visible, totalDur, onZoom, onHover, hover, showCritical = true, accent, onSvgLeave }: {
  defect: DefectRead;
  byTid: Record<string, { name: string; ts: number; dur: number; tid: string; ph: "X"; cat?: string }[]>;
  span: { start: number; end: number };
  visible: { start: number; end: number };
  totalDur: number;
  onZoom: (s: number, e: number) => void;
  onHover: (h: { x: number; y: number; event: { name: string; ts: number; dur: number; cat?: string }; laneName: string } | null) => void;
  hover: { x: number; y: number; event: { name: string; ts: number; dur: number; cat?: string }; laneName: string } | null;
  showCritical?: boolean;
  accent: string;
  onSvgLeave?: () => void;
}) {
  const ref = useRef<SVGSVGElement>(null);
  const [w, setW] = useState(1100);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(es => { for (const e of es) setW(e.contentRect.width); });
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);

  const LANE_H = 24, LANE_GAP = 2, GROUP_GAP = 18, GROUP_HEADER_H = 22;
  const labelW = 110, padR = 12, padT = 36;
  const innerW = Math.max(200, w - labelW - padR);

  const lanes: { kind: string; tid?: string; y: number; name?: string; hint?: string; label?: string }[] = [];
  let y = padT;
  for (const group of LANE_GROUPS) {
    lanes.push({ kind: "group", label: group.label, y });
    y += GROUP_HEADER_H;
    for (const tid of group.tids) {
      lanes.push({ kind: "lane", tid, y, ...(LANE_LABELS[tid] || {}) });
      y += LANE_H + LANE_GAP;
    }
    y += GROUP_GAP;
  }
  const totalH = y + 6;
  const us2x = (us: number) => labelW + ((us - visible.start) / totalDur) * innerW;

  const [dragStart, setDragStart] = useState<number | null>(null);
  const [dragEnd, setDragEnd] = useState<number | null>(null);
  const dragPan = useRef<{ startX: number; startVisible: { start: number; end: number } } | null>(null);
  const [isPanning, setIsPanning] = useState(false);

  // Wheel zoom anchored at cursor X position
  const onWheel = useCallback((e: React.WheelEvent<SVGSVGElement>) => {
    e.preventDefault();
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = (e.clientX - rect.left - labelW) / innerW;
    const anchorUs = visible.start + ratio * (visible.end - visible.start);
    const ZOOM_FACTOR = 0.12;
    const dir = e.deltaY > 0 ? 1 + ZOOM_FACTOR : 1 - ZOOM_FACTOR;
    const curSpan = visible.end - visible.start;
    const totalSpan = span.end - span.start;
    const minSpan = totalSpan > 0 ? totalSpan * 0.01 : 10000;
    const newSpan = Math.max(minSpan, Math.min(totalSpan, curSpan * dir));
    const anchorRatio = (anchorUs - visible.start) / curSpan;
    const newStart = Math.max(span.start, Math.min(span.end - newSpan, anchorUs - anchorRatio * newSpan));
    onZoom(newStart, Math.min(span.end, newStart + newSpan));
  }, [visible, labelW, innerW, span, onZoom]); // eslint-disable-line react-hooks/exhaustive-deps

  // Double-click resets to full range
  const onDoubleClick = useCallback(() => {
    onZoom(span.start, span.end);
  }, [span, onZoom]); // eslint-disable-line react-hooks/exhaustive-deps

  // MouseDown: left-drag pan (default) or Shift+drag box-select
  const onMouseDown = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (e.button !== 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    if (x < labelW) return;
    if (e.shiftKey) {
      setDragStart(x); setDragEnd(x);
      return;
    }
    dragPan.current = { startX: e.clientX, startVisible: { ...visible } };
    setIsPanning(true);
  }, [labelW, visible]);

  // MouseMove: pan or extend box-select
  const onMouseMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (dragPan.current) {
      const dpx = e.clientX - dragPan.current.startX;
      const sv = dragPan.current.startVisible;
      const dus = -(dpx / innerW) * (sv.end - sv.start);
      const spanLen = sv.end - sv.start;
      const newStart = Math.max(span.start, Math.min(span.end - spanLen, sv.start + dus));
      onZoom(newStart, Math.min(span.end, newStart + spanLen));
      return;
    }
    if (dragStart != null) {
      const rect = e.currentTarget.getBoundingClientRect();
      setDragEnd(e.clientX - rect.left);
    }
  }, [dragStart, innerW, span, onZoom]); // eslint-disable-line react-hooks/exhaustive-deps

  // MouseUp: finish pan or box-select zoom
  const onMouseUp = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (dragPan.current) {
      dragPan.current = null;
      setIsPanning(false);
      return;
    }
    if (dragStart == null) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const sX = Math.min(dragStart, x), eX = Math.max(dragStart, x);
    setDragStart(null); setDragEnd(null);
    if (eX - sX > 5) {
      const start_us = visible.start + ((sX - labelW) / innerW) * totalDur;
      const end_us = visible.start + ((eX - labelW) / innerW) * totalDur;
      onZoom(Math.max(span.start, start_us), Math.min(span.end, end_us));
    }
  }, [dragStart, visible, innerW, totalDur, span, onZoom]); // eslint-disable-line react-hooks/exhaustive-deps

  // MouseLeave: cancel any active interaction
  const onMouseLeave = useCallback(() => {
    if (dragPan.current) { dragPan.current = null; setIsPanning(false); }
    setDragStart(null); setDragEnd(null);
    onHover(null);
    onSvgLeave?.();
  }, [onHover, onSvgLeave]);

  const ticks = useMemo(() => {
    const ms = totalDur / 1000;
    let step_ms = 500;
    if (ms > 4000) step_ms = 500; else if (ms > 2000) step_ms = 250; else if (ms > 1000) step_ms = 200;
    else if (ms > 500) step_ms = 100; else if (ms > 200) step_ms = 50; else step_ms = 25;
    const step_us = step_ms * 1000;
    const start_ms = Math.floor(visible.start / step_us) * step_ms;
    const out: number[] = [];
    for (let t_ms = start_ms; t_ms * 1000 <= visible.end; t_ms += step_ms) out.push(t_ms);
    return out;
  }, [visible, totalDur]);

  return (
    <div style={{ position: "relative" }}>
      <svg ref={ref} width={w} height={totalH} tabIndex={0} onClick={() => ref.current?.focus({ preventScroll: true })} onWheel={onWheel} onDoubleClick={onDoubleClick} onMouseDown={onMouseDown} onMouseMove={onMouseMove} onMouseUp={onMouseUp} onMouseLeave={onMouseLeave} style={{ display: "block", outline: "none", cursor: dragStart != null ? "crosshair" : isPanning ? "grabbing" : "grab", userSelect: "none" }}>
        <g>
          {ticks.map((t_ms) => {
            const x = us2x(t_ms * 1000);
            return (
              <g key={t_ms}>
                <line x1={x} y1={padT - 14} x2={x} y2={totalH - 6} stroke="var(--line-soft)" strokeDasharray="1 3" />
                <text x={x} y={padT - 18} textAnchor="middle" fill="var(--fg-3)" style={{ fontFamily: "var(--font-mono)", fontSize: 9 }}>{t_ms}ms</text>
              </g>
            );
          })}
        </g>
        {lanes.map((ln, i) => {
          if (ln.kind === "group") {
            return (
              <g key={i}>
                <text x={6} y={ln.y + 12} fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">{ln.label}</text>
                <line x1={labelW} y1={ln.y + 14} x2={w - padR} y2={ln.y + 14} stroke="var(--line-soft)" strokeDasharray="2 4" />
              </g>
            );
          }
          return (
            <g key={i}>
              <rect x={0} y={ln.y} width={labelW - 2} height={LANE_H} fill="var(--bg-2)" />
              <text x={10} y={ln.y + 12} fontFamily="var(--font-mono)" fontSize="10" fill="var(--fg-1)" fontWeight="500">{ln.name || ln.tid}</text>
              <text x={10} y={ln.y + 22} fontFamily="var(--font-mono)" fontSize="8" fill="var(--fg-3)">{ln.hint || ""}</text>
              <rect x={labelW} y={ln.y} width={innerW} height={LANE_H} fill={i % 2 === 0 ? "rgba(255,255,255,0.012)" : "transparent"} />
              {(byTid[ln.tid!] || []).map((ev, j) => {
                const x = us2x(ev.ts);
                const wBar = Math.max(1.5, (ev.dur / totalDur) * innerW);
                if (x + wBar < labelW || x > w - padR) return null;
                const isCritical = showCritical && (ln.tid?.startsWith("NPU.") ?? false);
                const color = CAT_COLOR[ev.cat || ""] || "#888";
                return (
                  <g key={j}>
                    <rect x={x} y={ln.y! + 4} width={wBar} height={LANE_H - 8} fill={color}
                      opacity={showCritical && !isCritical ? 0.38 : 0.92}
                      style={isCritical ? { filter: `drop-shadow(0 0 3px ${color})` } : {}}
                      onMouseEnter={e => {
                        const svg = e.currentTarget.ownerSVGElement;
                        if (!svg) return;
                        const r = svg.getBoundingClientRect();
                        const ce = e.currentTarget.getBoundingClientRect();
                        onHover({ x: ce.left - r.left + ce.width / 2, y: ce.top - r.top, event: ev, laneName: ln.name || ln.tid || "" });
                      }}
                      onMouseLeave={() => onHover(null)}
                    />
                    {wBar > 60 && (
                      <text x={x + 4} y={ln.y! + LANE_H / 2 + 3} fontFamily="var(--font-mono)" fontSize="9" fill="var(--bg)" pointerEvents="none" style={{ fontWeight: 600 }}>
                        {ev.name.length > Math.floor(wBar / 6.5) ? ev.name.slice(0, Math.floor(wBar / 6.5)) + "…" : ev.name}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>
          );
        })}
        {dragStart != null && dragEnd != null && Math.abs(dragEnd - dragStart) > 2 && (
          <rect x={Math.min(dragStart, dragEnd)} y={padT - 14} width={Math.abs(dragEnd - dragStart)} height={totalH - padT - 4} fill={accent} opacity={0.12} stroke={accent} strokeOpacity={0.6} strokeDasharray="2 2" />
        )}
      </svg>
      {hover && <HoverTip hover={hover} containerWidth={w} />}
    </div>
  );
}
