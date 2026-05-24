"use client";

import React from "react";
import type { DefectRead, ActiveConfig } from "@/types/defect";
import type { DashboardStatsLike } from "@/types/stats";
import type { DataSourceStatus } from "@/lib/data-source";
import { KPITile, SectionHeader } from "./primitives";
import { RK3588Twin, FramePhase } from "./RK3588Twin";
import { FrameInspector } from "./FrameInspector";
import { RecentStream } from "./RecentStream";
import { CaveatBanner } from "./CaveatBanner";

interface OverviewProps {
  stats: DashboardStatsLike;
  defects: DefectRead[];
  phase: FramePhase;
  npuLoads: number[];
  cpuLoads: number[];
  ramUsed: number;
  twinMode: string;
  setTwinMode: (m: string) => void;
  selectedDefect: DefectRead | null;
  setSelectedDefect: (d: DefectRead | null) => void;
  onOpenProfile: (d: DefectRead) => void;
  activeConfig: ActiveConfig;
  accent?: string;
  dataSource?: DataSourceStatus;
  manifestCaveats?: string[];
}

export function OverviewPage({
  stats, defects, phase, npuLoads, cpuLoads, ramUsed,
  twinMode, setTwinMode, selectedDefect, setSelectedDefect,
  accent = "var(--acc)",
  dataSource,
  manifestCaveats,
}: OverviewProps) {
  const fps = "1.85";
  const e2eMs = Math.round(1000 / parseFloat(fps));
  const ttftAvg = Math.round(stats.ab_compare["2B_lora"]?.avg_ttft_ms || 1100);
  const jsonRate = Math.round(
    Object.values(stats.ab_compare).reduce((s, v) => s + (v.json_ok_rate || 0) * (v.count || 0), 0) /
    Math.max(1, Object.values(stats.ab_compare).reduce((s, v) => s + (v.count || 0), 0)) * 100,
  );

  return (
    <>
      {/* Hero */}
      <section>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "4px 12px", border: "1px solid var(--line)", borderRadius: 100, marginBottom: 18 }}>
          <span style={{ width: 6, height: 6, background: accent, borderRadius: "50%", boxShadow: `0 0 6px ${accent}` }} />
          <span className="mono" style={{ fontSize: 10, color: "var(--fg-2)", letterSpacing: "0.1em" }}>边缘节点 001 · RK3588 16GB · FastAPI + WS · Contract v1.2</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.3fr) minmax(0, 1fr)", gap: 60, alignItems: "flex-end" }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 52, fontWeight: 600, lineHeight: 1.04, letterSpacing: "-0.03em", color: "var(--fg)" }}>
              三阶段视觉流水线，
              <span style={{ display: "block", color: "var(--fg-3)" }}>量化部署在一块 <span style={{ color: accent }}>Orange Pi 5</span> 上。</span>
            </h1>
            <p style={{ color: "var(--fg-2)", fontSize: 15, lineHeight: 1.65, marginTop: 20, maxWidth: 620 }}>
              EfficientAD-S 门控异常，FastSAM-s bbox 提案，Qwen3-VL 输出结构化描述——全部运行在同一块 Rockchip RK3588 NPU 上，
              EAD/FastSAM FP16 · Qwen3-VL W8A8，跨三核异步流水线。前端仅消费 FastAPI REST + WebSocket，不直连 RK3588。
            </p>
            <div style={{ display: "flex", gap: 8, marginTop: 20, flexWrap: "wrap" }}>
              {["EAD/FastSAM FP16", "Qwen3-VL W8A8", "4 线程 C++ 流水线", "REST + WebSocket"].map(t => (
                <span key={t} className="mono" style={{ fontSize: 11, padding: "5px 11px", border: "1px solid var(--line)", background: "var(--bg-1)", color: "var(--fg-2)", letterSpacing: "0.04em", display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <span style={{ width: 4, height: 4, background: "var(--acc)" }} />{t}
                </span>
              ))}
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "var(--line)", border: "1px solid var(--line)" }}>
            <KPITile label="端到端延迟" value={e2eMs} unit="ms" sub="异常检测 → JSON" color={accent} />
            <KPITile label="VLM 首字延迟" value={ttftAvg} unit="ms" sub="Qwen3-VL · p50" />
            <KPITile label="JSON 解析率" value={jsonRate} unit="%" sub={`共 ${stats.total} 帧`} color="var(--ok)" />
            <KPITile label="LPDDR4 占用" value={ramUsed.toFixed(1)} unit="/ 16 GB" sub="VLM + 缓冲" />
          </div>
        </div>
      </section>

      {/* Data source + caveats */}
      {dataSource && (
        <CaveatBanner dataSource={dataSource} caveats={manifestCaveats} style="overview" />
      )}

      {/* Digital twin */}
      <section>
        <RK3588Twin phase={phase} npuLoads={npuLoads} cpuLoads={cpuLoads} ramUsed={ramUsed} mode={twinMode} onModeChange={setTwinMode} accent={accent} />
      </section>

      {/* Latest frame inspector */}
      <section style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <SectionHeader number="02" title="最新帧" caption="后端通过 POST /api/edge/report 收到的最新帧 · JSON / 指标 / 溯源" />
        <FrameInspector defect={defects[0] || null} />
      </section>

      {/* Detection feed */}
      <section style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <SectionHeader number="03" title="检测流" caption="来自 /ws/dashboard 的实时 WebSocket 流 · 点击卡片查看详情" />
        <RecentStream defects={defects} onSelect={setSelectedDefect} selectedId={selectedDefect?.id} />
      </section>
    </>
  );
}
