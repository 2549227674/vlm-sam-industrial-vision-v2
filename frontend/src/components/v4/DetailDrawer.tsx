"use client";

import React, { useEffect } from "react";
import type { DefectRead } from "@/types/defect";
import { fmtTime, fmtDateTime, variantLabel, variantColor } from "@/lib/mock-data";
import { SevPill, CatPill, VariantPill, FrameGantt, highlightJson, EnrichmentStatusBadge } from "./primitives";
import { FrameCanvas } from "./FrameInspector";
import { VlmDefectTooltip } from "./DataSourceBadge";

export interface EnrichmentState {
  status: "pending" | "running" | "complete" | "rejected" | "failed";
  provider?: string;
  observation_source?: string | null;
  error_message?: string | null;
  updated_at?: string;
}

interface DrawerProps {
  defect: DefectRead | null;
  onClose: () => void;
  onOpenProfile: (d: DefectRead) => void;
  enrichment?: EnrichmentState | null;
}

export function DetailDrawer({ defect, onClose, onOpenProfile, enrichment }: DrawerProps) {
  useEffect(() => {
    if (!defect) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [defect, onClose]);

  if (!defect) return null;
  const m = defect.vlm_metrics;
  const total = Math.round((defect.pipeline_ms.efficientad ?? 0) + (defect.pipeline_ms.fastsam ?? 0) + (defect.pipeline_ms.qwen3vl ?? 0) + (defect.pipeline_ms.localizer ?? 0) + (defect.pipeline_ms.upload ?? 0));

  return (
    <aside
      style={{
        position: "fixed", top: 0, right: 0, bottom: 0,
        width: 460, maxWidth: "100vw",
        background: "var(--bg-1)", borderLeft: "1px solid var(--line-hot)",
        boxShadow: "-1px 0 24px rgba(0,0,0,0.5)",
        display: "flex", flexDirection: "column",
        animation: "slide-in-right 0.18s ease-out both",
        zIndex: 50, overflow: "hidden",
      }}
    >
      <style>{`@keyframes slide-in-right { from { transform: translateX(20px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }`}</style>

      {/* Header */}
      <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--line)", background: "var(--bg-2)", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div className="eyebrow">缺陷详情 · {defect.line_id}</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 4 }}>
            <span className="mono" style={{ fontSize: 18, color: "var(--fg)", fontWeight: 600 }}>#{defect.id}</span>
            <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>· {fmtTime(defect.edge_ts)}</span>
          </div>
          <div style={{ display: "flex", gap: 5, marginTop: 8, flexWrap: "wrap" }}>
            <SevPill value={defect.severity} />
            <CatPill value={defect.category} />
            <VariantPill value={defect.variant} compact />
          </div>
        </div>
        <button onClick={onClose} style={{ background: "transparent", border: "1px solid var(--line)", color: "var(--fg-2)", padding: "4px 10px", fontFamily: "var(--font-mono)", fontSize: 11, cursor: "pointer" }}>ESC ✕</button>
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflowY: "auto", padding: 18, display: "flex", flexDirection: "column", gap: 16 }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: 8 }}>帧 · <VlmDefectTooltip defectType={defect.defect_type} /></div>
          <FrameCanvas defect={defect} aspect="16/10" />
        </div>
        <div>
          <div className="eyebrow" style={{ marginBottom: 8 }}>流水线 · {total} ms</div>
          <FrameGantt defect={defect} />
        </div>
        {m && (
          <div>
            <div className="eyebrow" style={{ marginBottom: 8 }}>VLM 指标 · {variantLabel(defect.variant)}</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "var(--line)", border: "1px solid var(--line)" }}>
              {[
                { l: "首字延迟", v: m.ttft_ms, u: "ms", c: variantColor(defect.variant) },
                { l: "解码速率", v: m.decode_tps.toFixed(2), u: "tok/s", c: "var(--acc)" },
                { l: "提示词元", v: m.prompt_tokens },
                { l: "输出词元", v: m.output_tokens },
                { l: "内存", v: m.rss_mb, u: "MB" },
                { l: "JSON 解析", v: m.json_parse_ok ? "OK" : "FAIL", c: m.json_parse_ok ? "var(--ok)" : "var(--crit)" },
              ].map((it) => (
                <div key={it.l} style={{ background: "var(--bg-1)", padding: "12px 14px" }}>
                  <div className="eyebrow" style={{ fontSize: 9 }}>{it.l}</div>
                  <div style={{ display: "flex", alignItems: "baseline", gap: 3, marginTop: 5 }}>
                    <span className="mono" style={{ fontSize: 18, fontWeight: 500, color: it.c || "var(--fg)", letterSpacing: "-0.01em" }}>{it.v}</span>
                    {it.u && <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>{it.u}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        {/* Enrichment state section */}
        {(enrichment || defect.observation_source) && (
          <div>
            <div className="eyebrow" style={{ marginBottom: 8, display: "flex", alignItems: "center", gap: 8 }}>
              VLM Enrichment
              {enrichment && <EnrichmentStatusBadge status={enrichment.status} provider={enrichment.provider} />}
              {!enrichment && defect.observation_source && <EnrichmentStatusBadge status="complete" provider={defect.observation_source} />}
            </div>
            <div style={{ border: "1px solid var(--line)", padding: "4px 0" }}>
              {enrichment?.status === "complete" || (!enrichment && defect.observation_source) ? (
                <>
                  <div style={{ padding: "8px 12px", borderBottom: "1px solid var(--line)" }}>
                    <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", display: "block", marginBottom: 4 }}>Observation</span>
                    <span style={{ fontSize: 11, color: "var(--fg-1)", lineHeight: 1.5 }}>{defect.observation || defect.description}</span>
                  </div>
                  {defect.severity_reason && (
                    <div style={{ padding: "8px 12px", borderBottom: "1px solid var(--line)" }}>
                      <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", display: "block", marginBottom: 4 }}>Severity Reason</span>
                      <span style={{ fontSize: 11, color: "var(--fg-2)", lineHeight: 1.5 }}>{defect.severity_reason}</span>
                    </div>
                  )}
                </>
              ) : enrichment?.status === "pending" || enrichment?.status === "running" ? (
                <div style={{ padding: "10px 12px" }}>
                  <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>
                    {enrichment.status === "pending" ? "Queued for enrichment…" : "Processing…"}
                  </span>
                  <div style={{ marginTop: 6, fontSize: 10, color: "var(--fg-4)", lineHeight: 1.5 }}>
                    Current observation is template/detector output. EdgeVLM result will replace observation and severity_reason only.
                  </div>
                </div>
              ) : (
                <div style={{ padding: "10px 12px" }}>
                  <span className="mono" style={{ fontSize: 10, color: enrichment?.status === "rejected" ? "var(--warn)" : "var(--crit)" }}>
                    {enrichment?.status === "rejected" ? "Enrichment rejected — guard validation failed" : "Enrichment failed"}
                  </span>
                  {enrichment?.error_message && (
                    <div style={{ marginTop: 4, fontSize: 10, color: "var(--fg-3)" }}>{enrichment.error_message}</div>
                  )}
                  <div style={{ marginTop: 6, fontSize: 10, color: "var(--fg-4)", lineHeight: 1.5 }}>
                    Falling back to template observation. EdgeVLM does not modify geometry or canonical label.
                  </div>
                </div>
              )}
              <div style={{ padding: "6px 12px", borderTop: "1px dashed var(--line-soft)" }}>
                <span className="mono" style={{ fontSize: 9, color: "var(--fg-4)", lineHeight: 1.4 }}>
                  VLM enrichment is narrative-only: observation / severity_reason / observation_source. BBox, category, defect_type, confidence, anomaly_score are unchanged.
                </span>
              </div>
            </div>
          </div>
        )}
        <div>
          <div className="eyebrow" style={{ marginBottom: 8 }}>JSON</div>
          <pre style={{ margin: 0, padding: "12px 14px", background: "#08080c", border: "1px solid var(--line)", fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--fg-1)", lineHeight: 1.6, whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 220, overflow: "auto" }}
            dangerouslySetInnerHTML={{ __html: JSON.stringify({ category: defect.category, defect_type: defect.defect_type, severity: defect.severity, confidence: defect.confidence, bboxes: defect.bboxes, description: defect.description }, null, 2).split("\n").map(l => highlightJson(l)).join("\n") }}
          />
        </div>
        <div>
          <div className="eyebrow" style={{ marginBottom: 8 }}>溯源</div>
          <div style={{ border: "1px solid var(--line)", padding: "4px 0" }}>
            {[["边缘时间戳", fmtDateTime(defect.edge_ts)], ["服务器时间戳", fmtDateTime(defect.server_ts)], ["图像路径", defect.image_url], ["版本", defect.schema_version]].map(([k, v]) => (
              <div key={k} style={{ display: "grid", gridTemplateColumns: "100px 1fr", padding: "5px 12px" }}>
                <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>{k}</span>
                <span className="mono" style={{ fontSize: 10, color: "var(--fg-1)", wordBreak: "break-all" }}>{v}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div style={{ borderTop: "1px solid var(--line)", padding: "12px 18px", background: "var(--bg-2)", display: "flex", justifyContent: "space-between", gap: 8 }}>
        <button onClick={() => onOpenProfile(defect)} style={{ background: "var(--acc)", color: "var(--bg)", border: "none", padding: "8px 14px", fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: "0.1em", fontWeight: 700, textTransform: "uppercase", cursor: "pointer" }}>在性能剖析中打开 →</button>
        <button onClick={onClose} style={{ background: "transparent", border: "1px solid var(--line)", color: "var(--fg-2)", padding: "8px 14px", fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: "0.1em", fontWeight: 600, textTransform: "uppercase", cursor: "pointer" }}>关闭</button>
      </div>
    </aside>
  );
}
