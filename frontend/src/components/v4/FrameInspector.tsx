"use client";

import React, { useState, useEffect } from "react";
import type { DefectRead } from "@/types/defect";
import { fmtTime, fmtDateTime, variantLabel, variantColor, variantModel } from "@/lib/mock-data";
import { SevPill, CatPill, VariantPill, FrameGantt, SimulatedSample, RealImageWithFallback, highlightJson } from "./primitives";
import { VlmDefectTooltip } from "./DataSourceBadge";

// ── FrameInspector ──────────────────────────────────────────────────────────

export function FrameInspector({ defect }: { defect: DefectRead | null }) {
  const [tab, setTab] = useState<"json" | "metrics" | "provenance">("json");
  if (!defect) {
    return (
      <div style={{ background: "var(--bg-1)", border: "1px solid var(--line)", padding: 40, textAlign: "center", color: "var(--fg-3)" }}>
        <span className="mono" style={{ fontSize: 12 }}>等待首帧…</span>
      </div>
    );
  }
  return (
    <div style={{ background: "var(--bg-1)", border: "1px solid var(--line)", display: "grid", gridTemplateColumns: "minmax(0,1.1fr) minmax(0,1fr)" }}>
      <FramePane defect={defect} />
      <RightPane defect={defect} tab={tab} setTab={setTab} />
    </div>
  );
}

function FramePane({ defect }: { defect: DefectRead }) {
  const total = Math.round(defect.pipeline_ms.efficientad + defect.pipeline_ms.fastsam + defect.pipeline_ms.qwen3vl);
  return (
    <div style={{ padding: 18, borderRight: "1px solid var(--line)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 12 }}>
        <div>
          <div className="eyebrow">最新帧 · {defect.line_id}</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 4 }}>
            <span className="mono" style={{ fontSize: 18, color: "var(--fg)", fontWeight: 600 }}>#{defect.id}</span>
            <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>· {fmtTime(defect.edge_ts)}</span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap", justifyContent: "flex-end" }}>
          <SevPill value={defect.severity} />
          <CatPill value={defect.category} />
          <VariantPill value={defect.variant} />
        </div>
      </div>
      <FrameCanvas defect={defect} cornerLabels />
      <div style={{ marginTop: 14 }}>
        <div className="eyebrow" style={{ marginBottom: 6 }}>流水线耗时 · {total} ms</div>
        <FrameGantt defect={defect} />
      </div>
    </div>
  );
}

// FrameCanvas — reusable in inspector, drawer, cards
export function FrameCanvas({ defect, cornerLabels = false, aspect = "4/3" }: { defect: DefectRead; cornerLabels?: boolean; aspect?: string }) {
  return (
    <div style={{ position: "relative", width: "100%", aspectRatio: aspect, background: "var(--bg)", border: "1px solid var(--line)", overflow: "hidden" }}>
      <RealImageWithFallback imageUrl={defect.image_url} category={defect.category} showBadge={cornerLabels} />
      <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: 2, background: "linear-gradient(90deg, transparent, var(--acc), transparent)", opacity: 0.5, animation: "scan-line 4s linear infinite" }} />
      {cornerLabels && (
        <>
          <div style={{ position: "absolute", top: 8, left: 10, fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--acc)", letterSpacing: "0.1em", textShadow: "0 0 6px var(--acc-glow)" }}>CAM-{defect.line_id} · 1280×1024</div>
          <div style={{ position: "absolute", top: 8, right: 10, fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--warn)" }}>σ = {defect.anomaly_score}</div>
          <div style={{ position: "absolute", bottom: 8, left: 10, fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--fg-2)" }}>{defect.image_url.split("/").slice(-1)[0]}</div>
          <div style={{ position: "absolute", bottom: 8, right: 10, display: "flex", alignItems: "center", gap: 5, fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--ok)" }}>
            <span style={{ width: 5, height: 5, background: "var(--ok)", borderRadius: "50%", animation: "pulse-dot 1.4s infinite" }} /> REC
          </div>
        </>
      )}
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position: "absolute", inset: 0, width: "100%", height: "100%", overflow: "visible" }}>
        {defect.bboxes.map((b, i) => {
          // Clamp bbox to [0, 1] range to prevent SVG overflow
          const x = Math.max(0, Math.min(100, b.x * 100));
          const y = Math.max(0, Math.min(100, b.y * 100));
          const w = Math.min(100 - x, b.w * 100);
          const h = Math.min(100 - y, b.h * 100);
          const isClamped = b.x + b.w > 1 || b.y + b.h > 1 || b.x < 0 || b.y < 0;
          return (
            <g key={i}>
              <rect x={x} y={y} width={w} height={h} fill="color-mix(in srgb, var(--acc) 8%, transparent)" stroke="var(--acc)" strokeWidth="0.2" vectorEffect="non-scaling-stroke" />
              {cornerLabels && (
                <foreignObject x={x} y={Math.max(0, y - 4)} width={Math.max(w, 20)} height="4">
                  <div style={{ display: "inline-block", fontFamily: "var(--font-mono)", fontSize: 8, color: "var(--bg)", background: "var(--acc)", padding: "1px 4px", letterSpacing: "0.06em", fontWeight: 700 } as React.CSSProperties}>
                    <span title="Proposal bbox from FastSAM/VLM. Not verified ground-truth localization. / FastSAM/VLM 候选框，非可靠定位。" style={{ cursor: "help" }}>
                      {defect.defect_type}<span style={{ opacity: 0.6, marginLeft: 4 }}>{(defect.confidence * 100).toFixed(0)}</span>
                    </span>
                  </div>
                </foreignObject>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ── Right pane (JSON / Metrics / Provenance) ────────────────────────────────

function RightPane({ defect, tab, setTab }: { defect: DefectRead; tab: string; setTab: (t: "json" | "metrics" | "provenance") => void }) {
  return (
    <div style={{ padding: 18, background: "linear-gradient(180deg, var(--bg-1) 0%, #0a0a10 100%)", display: "flex", flexDirection: "column", gap: 12, minHeight: 0 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div>
          <div className="eyebrow">VLM 输出 · {variantModel(defect.variant)} · {variantLabel(defect.variant)}</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 4 }}>
            <span style={{ fontSize: 14, color: "var(--fg)", fontWeight: 500 }}>
              {tab === "json" ? "JSON 流输出" : tab === "metrics" ? "VLM 指标" : "溯源"}
            </span>
          </div>
        </div>
        <div style={{ display: "inline-flex", border: "1px solid var(--line)", background: "var(--bg-1)" }}>
          {(["json", "metrics", "provenance"] as const).map((t, i) => {
            const active = tab === t;
            const labels = { json: "JSON", metrics: "指标", provenance: "溯源" };
            return (
              <button key={t} onClick={() => setTab(t)} style={{
                padding: "5px 12px", fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.12em",
                fontWeight: 600, textTransform: "uppercase",
                background: active ? "var(--acc)" : "transparent", color: active ? "var(--bg)" : "var(--fg-2)",
                border: "none", borderRight: i < 2 ? "1px solid var(--line)" : "none", cursor: "pointer",
              }}>{labels[t]}</button>
            );
          })}
        </div>
      </div>
      {tab === "json" && <JsonTab defect={defect} />}
      {tab === "metrics" && <MetricsTab defect={defect} />}
      {tab === "provenance" && <ProvenanceTab defect={defect} />}
    </div>
  );
}

function JsonTab({ defect }: { defect: DefectRead }) {
  const [pos, setPos] = useState(0);
  const target = JSON.stringify({
    category: defect.category, defect_type: defect.defect_type, severity: defect.severity,
    confidence: defect.confidence, bboxes: defect.bboxes.map(b => ({ x: +b.x.toFixed(3), y: +b.y.toFixed(3), w: +b.w.toFixed(3), h: +b.h.toFixed(3) })),
    description: defect.description?.trim() ? defect.description : "(omitted by compact VLM output)",
  }, null, 2);

  useEffect(() => {
    setPos(0);
    let p = 0;
    const id = setInterval(() => {
      p += Math.floor(3 + Math.random() * 4);
      if (p >= target.length) { setPos(target.length); clearInterval(id); }
      else setPos(p);
    }, 24);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defect.id]);

  const done = pos >= target.length;
  const lines = target.slice(0, pos).split("\n");

  return (
    <div style={{ flex: 1, position: "relative", background: "#08080c", border: "1px solid var(--line)", padding: "14px 16px", fontFamily: "var(--font-mono)", fontSize: 12, lineHeight: 1.7, minHeight: 320, overflow: "hidden" }}>
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 22, background: "var(--bg-2)", borderBottom: "1px solid var(--line-soft)", display: "flex", alignItems: "center", padding: "0 10px", gap: 5 }}>
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#ff6378" }} />
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#ffbf5c" }} />
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#6dffac" }} />
        <span className="mono" style={{ marginLeft: 10, fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.1em" }}>vlm_output.json · {variantLabel(defect.variant)}</span>
        <span style={{ flex: 1 }} />
        <span className="mono" style={{ fontSize: 9, color: done && defect.vlm_metrics?.json_parse_ok ? "var(--ok)" : "var(--warn)" }}>
          {!done ? "● 流输出中" : defect.vlm_metrics?.json_parse_ok ? "✓ 已解析" : "✗ 重试"}
        </span>
      </div>
      <pre style={{ margin: 0, paddingTop: 18, color: "var(--fg-1)", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
        {lines.map((line, i) => (
          <div key={i} style={{ display: "flex" }}>
            <span style={{ width: 28, color: "var(--fg-4)", textAlign: "right", paddingRight: 10, userSelect: "none" }}>{String(i + 1).padStart(2, " ")}</span>
            <span style={{ flex: 1 }} dangerouslySetInnerHTML={{ __html: highlightJson(line) }} />
          </div>
        ))}
        {!done && <span style={{ display: "inline-block", width: 8, height: 12, marginLeft: 38, background: "var(--acc)", verticalAlign: "middle", animation: "blink-cursor 0.8s infinite" }} />}
      </pre>
    </div>
  );
}

function MetricsTab({ defect }: { defect: DefectRead }) {
  const m = defect.vlm_metrics;
  if (!m) return <div style={{ color: "var(--fg-3)", padding: 20 }}>No VLM metrics</div>;
  const items = [
    { l: "首字延迟", v: m.ttft_ms, u: "ms", c: variantColor(defect.variant), big: true },
    { l: "解码速率", v: m.decode_tps.toFixed(2), u: "tok/s", c: "var(--acc)", big: true },
    { l: "提示词元", v: m.prompt_tokens, u: "" },
    { l: "输出词元", v: m.output_tokens, u: "" },
    { l: "VLM 内存", v: m.rss_mb, u: "MB" },
    { l: "异常分数 σ", v: defect.anomaly_score, u: "", c: "var(--warn)" },
    { l: "置信度", v: (defect.confidence * 100).toFixed(1), u: "%" },
    { l: "JSON 解析", v: m.json_parse_ok ? "OK" : "FAIL", u: "", c: m.json_parse_ok ? "var(--ok)" : "var(--crit)" },
  ];
  return (
    <div style={{ flex: 1, background: "var(--bg-1)", border: "1px solid var(--line)", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, backgroundColor: "var(--line)", minHeight: 320 }}>
      {items.map((it) => (
        <div key={it.l} style={{ background: "var(--bg-1)", padding: "14px 16px" }}>
          <div className="eyebrow" style={{ fontSize: 9 }}>{it.l}</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginTop: 6 }}>
            <span className="mono" style={{ fontSize: it.big ? 26 : 18, fontWeight: 500, color: it.c || "var(--fg)", letterSpacing: "-0.01em", fontVariantNumeric: "tabular-nums" }}>{it.v}</span>
            {it.u && <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>{it.u}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

function ProvenanceTab({ defect }: { defect: DefectRead }) {
  const rows: [string, string][] = [
    ["ID", `#${defect.id}`],
    ["生产线", defect.line_id],
    ["类别", defect.category],
    ["缺陷类型", defect.defect_type],
    ["变体", defect.variant],
    ["边缘时间戳", fmtDateTime(defect.edge_ts)],
    ["服务器时间戳", fmtDateTime(defect.server_ts)],
    ["图像路径", defect.image_url],
    ["版本", defect.schema_version],
    ["追踪事件", `${defect.trace_events?.length ?? 0} 条`],
  ];
  return (
    <div style={{ flex: 1, background: "var(--bg-1)", border: "1px solid var(--line)", padding: "12px 0", minHeight: 320, overflow: "auto" }}>
      {rows.map(([k, v]) => (
        <div key={k} style={{ display: "grid", gridTemplateColumns: "140px 1fr", padding: "7px 16px", borderBottom: "1px solid var(--line-soft)" }}>
          <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>{k}</span>
          <span className="mono" style={{ fontSize: 11, color: "var(--fg-1)", wordBreak: "break-all" }}>{v}</span>
        </div>
      ))}
    </div>
  );
}
