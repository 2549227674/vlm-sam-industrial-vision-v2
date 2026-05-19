"use client";

import React, { useState, useEffect, useCallback } from "react";
import { seedDefects, buildStats, makeDefect } from "@/lib/mock-data";
import type { DefectRead, ActiveConfig } from "@/types/defect";

import { TopBar } from "@/components/v4/TopBar";
import { BottomBar } from "@/components/v4/BottomBar";
import { OverviewPage } from "@/components/v4/OverviewPage";
import { ProfilePage } from "@/components/v4/ProfilePage";
import { ABMatrix } from "@/components/v4/ABMatrix";
import { ModelsPage } from "@/components/v4/ModelsPage";
import { LogsPage } from "@/components/v4/LogsPage";
import { DetailDrawer } from "@/components/v4/DetailDrawer";
import { useFrameSimulator, useCpuLoads, useNpuLoads } from "@/components/v4/RK3588Twin";

export default function Dashboard() {
  // Routing
  const [route, setRoute] = useState(() =>
    typeof window !== "undefined" ? (window.location.hash.replace("#", "") || "overview") : "overview"
  );

  useEffect(() => {
    const onHash = () => setRoute(window.location.hash.replace("#", "") || "overview");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const navigate = useCallback((key: string) => { window.location.hash = "#" + key; }, []);

  // Global state
  const [defects, setDefects] = useState<DefectRead[]>([]);
  const [now, setNow] = useState(new Date());
  const [selectedDefect, setSelectedDefect] = useState<DefectRead | null>(null);
  const [profileSeedIdx, setProfileSeedIdx] = useState(0);
  const [activeConfig, setActiveConfig] = useState<ActiveConfig>({ model_size: "2B", variant: "lora" });
  const [twinMode, setTwinMode] = useState("xray");
  const [live] = useState(true);
  const [tracePaused, setTracePaused] = useState(false);

  // Clock
  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  // Mock data init
  useEffect(() => {
    setDefects(seedDefects(80));
  }, []);

  // Frame simulator + loads
  const npuLoads = useNpuLoads();
  const phase = useFrameSimulator({
    live,
    onComplete: () => {
      if (tracePaused) return;
      const d = makeDefect({ ts: new Date() });
      setDefects(prev => [d, ...prev].slice(0, 100));
    },
  });
  const cpuLoads = useCpuLoads(phase);

  const stats = buildStats(defects);
  const ramUsed = (activeConfig.model_size === "4B" ? 11.4 : 5.0) + (npuLoads[2] / 100) * 0.6;

  const openProfileForDefect = useCallback((d: DefectRead) => {
    const idx = defects.findIndex(x => x.id === d.id);
    setProfileSeedIdx(idx >= 0 ? idx : 0);
    setSelectedDefect(null);
    navigate("profile");
  }, [defects, navigate]);

  return (
    <div style={{ minHeight: "100vh" }}>
      <TopBar now={now} live={live} route={route} navigate={navigate} />

      <main style={{ maxWidth: 1480, margin: "0 auto", padding: "20px 32px 80px", display: "flex", flexDirection: "column", gap: 28 }}>
        {route === "overview" && (
          <OverviewPage
            stats={stats} defects={defects}
            phase={phase} npuLoads={npuLoads} cpuLoads={cpuLoads}
            ramUsed={ramUsed}
            twinMode={twinMode} setTwinMode={setTwinMode}
            selectedDefect={selectedDefect} setSelectedDefect={setSelectedDefect}
            onOpenProfile={openProfileForDefect}
            activeConfig={activeConfig}
          />
        )}

        {route === "profile" && (
          <>
            <section style={{ paddingTop: 0 }}>
              <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "4px 12px", border: "1px solid var(--line)", borderRadius: 100, marginBottom: 18 }}>
                <span style={{ width: 6, height: 6, background: "var(--acc)", borderRadius: "50%", boxShadow: "0 0 6px var(--acc)" }} />
                <span className="mono" style={{ fontSize: 10, color: "var(--fg-2)", letterSpacing: "0.1em" }}>性能剖析 · 瓶颈分析</span>
              </div>
              <h1 style={{ margin: 0, fontSize: 44, fontWeight: 600, lineHeight: 1.05, letterSpacing: "-0.025em" }}>
                逐帧时序分析，
                <span style={{ display: "block", color: "var(--fg-3)" }}>横跨 <span style={{ color: "var(--acc)" }}>4 线程 · 3 NPU 核 · 8 ARM 核</span>。</span>
              </h1>
              <p style={{ color: "var(--fg-2)", fontSize: 15, lineHeight: 1.65, marginTop: 16, maxWidth: 720 }}>
                聚焦瓶颈，逐帧分析：Chrome-trace 精度追踪每一个事件，NPU.2（Qwen3-VL）——占关键路径的 98%，但仅需 1ms 无需过度优化。
              </p>
            </section>
            <ProfilePage defects={defects} initialFrameIdx={profileSeedIdx} onTraceHoverChange={setTracePaused} />
          </>
        )}

        {route === "ab" && (
          <>
            <section style={{ paddingTop: 0 }}>
              <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "4px 12px", border: "1px solid var(--line)", borderRadius: 100, marginBottom: 18 }}>
                <span style={{ width: 6, height: 6, background: "var(--acc)", borderRadius: "50%", boxShadow: "0 0 6px var(--acc)" }} />
                <span className="mono" style={{ fontSize: 10, color: "var(--fg-2)", letterSpacing: "0.1em" }}>变体对比 · 矩阵分析</span>
              </div>
              <h1 style={{ margin: 0, fontSize: 44, fontWeight: 600, lineHeight: 1.05, letterSpacing: "-0.025em" }}>
                四个变体，
                <span style={{ display: "block", color: "var(--fg-3)" }}>一个<span style={{ color: "var(--acc)" }}>已部署</span>方案。</span>
              </h1>
            </section>
            <ABMatrix stats={stats} activeConfig={activeConfig} />
          </>
        )}

        {route === "models" && (
          <ModelsPage activeConfig={activeConfig} onChangeConfig={setActiveConfig} />
        )}

        {route === "logs" && (
          <LogsPage />
        )}
      </main>

      <BottomBar now={now} live={live} route={route} activeConfig={activeConfig} totalDefects={defects.length} />

      <DetailDrawer
        defect={selectedDefect}
        onClose={() => setSelectedDefect(null)}
        onOpenProfile={openProfileForDefect}
      />
    </div>
  );
}
