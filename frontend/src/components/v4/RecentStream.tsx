"use client";

import React, { useState, useMemo } from "react";
import type { DefectRead } from "@/types/defect";
import { fmtTime, MVTEC_CATEGORIES, CATEGORY_LABEL, VARIANTS, VARIANT_LABEL, normalizeVariant } from "@/lib/mock-data";
import { SevPill, VariantPill, SimulatedSample, RealImageWithFallback } from "./primitives";
import { VlmDefectTooltip } from "./DataSourceBadge";

interface StreamProps {
  defects: DefectRead[];
  onSelect: (d: DefectRead) => void;
  selectedId?: number | null;
}

export function RecentStream({ defects, onSelect, selectedId }: StreamProps) {
  const [sev, setSev] = useState("all");
  const [cat, setCat] = useState("all");
  const [vr, setVr] = useState("all");

  const filtered = useMemo(() => {
    return defects.filter((d) => {
      if (sev !== "all" && d.severity !== sev) return false;
      if (cat !== "all" && d.category !== cat) return false;
      if (vr !== "all" && normalizeVariant(d.variant) !== vr) return false;
      return true;
    });
  }, [defects, sev, cat, vr]);

  const shown = filtered.slice(0, 12);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 18, gap: 16, flexWrap: "wrap" }}>
        <div>
          <div className="eyebrow">最近检测</div>
          <h2 style={{ margin: 0, marginTop: 6, fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em" }}>
            最近 <span className="mono" style={{ color: "var(--acc)" }}>{shown.length}</span>
            <span style={{ color: "var(--fg-3)", fontWeight: 400 }}> / {filtered.length} 帧</span>
          </h2>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <SegFilter value={sev} onChange={setSev} options={[["all", "全部"], ["high", "高"], ["medium", "中"], ["low", "低"]]} />
          <FilterSelect label="类别" value={cat} onChange={setCat} options={[["all", "全部 15 类"], ...MVTEC_CATEGORIES.map((c): [string, string] => [c, CATEGORY_LABEL[c]])]} />
          <FilterSelect label="变体" value={vr} onChange={setVr} options={[["all", "全部变体"], ...VARIANTS.map((v): [string, string] => [v, VARIANT_LABEL[v]])]} />
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 1, background: "var(--line)", border: "1px solid var(--line)" }}>
        {shown.map((d) => (
          <DetectionCard key={d.id} defect={d} selected={d.id === selectedId} onClick={() => onSelect(d)} />
        ))}
        {!shown.length && (
          <div style={{ background: "var(--bg-1)", padding: 40, textAlign: "center", color: "var(--fg-3)" }}>
            <span className="mono" style={{ fontSize: 12 }}>没有符合条件的帧。</span>
          </div>
        )}
      </div>
    </div>
  );
}

function SegFilter({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <div style={{ display: "inline-flex", border: "1px solid var(--line)" }}>
      {options.map(([v, l], i) => {
        const active = value === v;
        return (
          <button key={v} onClick={() => onChange(v)} style={{
            padding: "5px 11px", fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.1em",
            fontWeight: 600, textTransform: "uppercase",
            background: active ? "var(--acc)" : "transparent", color: active ? "var(--bg)" : "var(--fg-2)",
            border: "none", borderRight: i < options.length - 1 ? "1px solid var(--line)" : "none", cursor: "pointer",
          }}>{l}</button>
        );
      })}
    </div>
  );
}

function FilterSelect({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <label style={{ display: "inline-flex", alignItems: "center", gap: 6, border: "1px solid var(--line)", padding: "3px 6px 3px 10px", background: "var(--bg-1)" }}>
      <span className="eyebrow" style={{ fontSize: 9 }}>{label}</span>
      <select value={value} onChange={e => onChange(e.target.value)} style={{ fontFamily: "var(--font-mono)", fontSize: 11, background: "var(--bg-1)", color: "var(--fg-1)", border: "none", outline: "none", padding: "3px 6px", cursor: "pointer" }}>
        {options.map(([v, l]) => <option key={v} value={v} style={{ background: "var(--bg-1)", color: "var(--fg-1)" }}>{l}</option>)}
      </select>
    </label>
  );
}

function DetectionCard({ defect, selected, onClick }: { defect: DefectRead; selected: boolean; onClick: () => void }) {
  const total = Math.round(defect.pipeline_ms.efficientad + defect.pipeline_ms.fastsam + defect.pipeline_ms.qwen3vl);
  const sevColor = { low: "var(--ok)", medium: "var(--warn)", high: "var(--crit)" }[defect.severity];

  return (
    <button onClick={onClick} style={{
      background: selected ? "var(--bg-2)" : "var(--bg-1)", border: "none",
      borderLeft: selected ? "3px solid var(--acc)" : "3px solid transparent",
      padding: 14, textAlign: "left", cursor: "pointer",
      display: "flex", flexDirection: "column", gap: 10,
      transition: "background 0.12s", position: "relative",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span className="mono" style={{ fontSize: 11, color: "var(--fg-2)" }}>#{defect.id}</span>
        <span style={{ display: "flex", gap: 4 }}>
          <SevPill value={defect.severity} />
          <VariantPill value={defect.variant} compact />
        </span>
      </div>
      <div style={{ position: "relative", width: "100%", aspectRatio: "16/10", background: "var(--bg)", border: "1px solid var(--line)", overflow: "hidden" }}>
        <RealImageWithFallback imageUrl={defect.image_url} category={defect.category} />
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
          {defect.bboxes.slice(0, 2).map((b, i) => (
            <rect key={i} x={b.x * 100} y={b.y * 100} width={b.w * 100} height={b.h * 100} fill="none" stroke={sevColor} strokeWidth="0.3" vectorEffect="non-scaling-stroke" />
          ))}
        </svg>
        <div style={{ position: "absolute", top: 4, left: 6, fontFamily: "var(--font-mono)", fontSize: 8, color: "var(--fg-3)" }}>{defect.line_id} · {CATEGORY_LABEL[defect.category] || defect.category}</div>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={{ fontSize: 13, color: "var(--fg)", fontWeight: 500 }}><VlmDefectTooltip defectType={defect.defect_type} /></span>
        <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>{(defect.confidence * 100).toFixed(0)}%</span>
      </div>
      <div style={{ display: "flex", height: 4, background: "var(--bg-3)" }}>
        <div style={{ width: `${(defect.pipeline_ms.efficientad / total) * 100}%`, background: "var(--core-0)" }} />
        <div style={{ width: `${(defect.pipeline_ms.fastsam / total) * 100}%`, background: "var(--core-1)" }} />
        <div style={{ width: `${(defect.pipeline_ms.qwen3vl / total) * 100}%`, background: "var(--core-2)" }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>{fmtTime(defect.edge_ts)}</span>
        <span className="mono" style={{ fontSize: 10, color: total > 2400 ? "var(--warn)" : "var(--fg-2)" }}>Σ {total}ms</span>
      </div>
    </button>
  );
}
