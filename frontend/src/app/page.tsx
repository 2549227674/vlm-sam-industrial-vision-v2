"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { buildStats, makeDefect } from "@/lib/mock-data";
import type { DefectRead, ActiveConfig } from "@/types/defect";
import type { DashboardStatsLike } from "@/types/stats";
import { useDefectWebSocket, type EnrichmentUpdate } from "@/lib/ws";
import { getDefectEnrichment } from "@/lib/api";
import { useDataSource, type DataSourceStatus } from "@/lib/data-source";

import { TopBar } from "@/components/v4/TopBar";
import { BottomBar } from "@/components/v4/BottomBar";
import { OverviewPage } from "@/components/v4/OverviewPage";
import { ProfilePage } from "@/components/v4/ProfilePage";
import { ABMatrix } from "@/components/v4/ABMatrix";
import { ModelsPage } from "@/components/v4/ModelsPage";
import { LogsPage } from "@/components/v4/LogsPage";
import { DetailDrawer } from "@/components/v4/DetailDrawer";
import type { EnrichmentState } from "@/components/v4/DetailDrawer";
import { useFrameSimulator, useCpuLoads, useNpuLoads } from "@/components/v4/RK3588Twin";

export default function Dashboard() {
  // Routing — always start with "overview" to match SSR, then sync to hash after hydration
  const [route, setRoute] = useState("overview");

  useEffect(() => {
    const sync = () => setRoute(window.location.hash.replace("#", "") || "overview");
    sync();
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  const navigate = useCallback((key: string) => { window.location.hash = "#" + key; }, []);

  // Data source — Live API > Real Snapshot > Mock
  const { defects: dsDefects, stats: dsStats, status: dsStatus, manifest, refresh } = useDataSource();

  // Defects state — merged from data source + WS updates
  const [defects, setDefects] = useState<DefectRead[]>([]);
  const [wsDefects, setWsDefects] = useState<DefectRead[]>([]);
  const [apiStats, setApiStats] = useState<DashboardStatsLike | null>(null);
  const [now, setNow] = useState<Date | null>(null);
  const [selectedDefect, setSelectedDefect] = useState<DefectRead | null>(null);
  const [profileSeedIdx, setProfileSeedIdx] = useState(0);
  const [activeConfig, setActiveConfig] = useState<ActiveConfig>({ model_size: "2B", variant: "lora" });
  const [twinMode, setTwinMode] = useState("xray");

  // Enrichment state — keyed by defect_id
  const [enrichmentMap, setEnrichmentMap] = useState<Map<number, EnrichmentState>>(new Map());

  // Sync data source defects into local state
  useEffect(() => {
    setDefects(dsDefects);
  }, [dsDefects]);

  // Track if we ever had a live connection (for WS reconnecting state)
  const [everHadLive, setEverHadLive] = useState(false);
  useEffect(() => {
    if (dsStatus.kind === "live") setEverHadLive(true);
  }, [dsStatus.kind]);

  // Effective data source status (overlay WS reconnecting if live was detected)
  const dataSourceStatus: DataSourceStatus = useMemo(() => {
    if (everHadLive && dsStatus.kind === "mock") {
      return {
        kind: "reconnecting",
        label: "WebSocket 重连中",
        labelEn: "Reconnecting",
        color: "var(--warn)",
        description: "Lost connection to live backend. Attempting to reconnect.",
      };
    }
    return dsStatus;
  }, [dsStatus, everHadLive]);

  // Clock
  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  // Frame simulator + loads
  const npuLoads = useNpuLoads();
  const isSimulatorMode = dataSourceStatus.kind === "mock";
  const phase = useFrameSimulator({
    live: true,
    onComplete: () => {
      if (!isSimulatorMode) return;
      const d = makeDefect({ ts: new Date() });
      setDefects(prev => [d, ...prev].slice(0, 100));
    },
  });
  const cpuLoads = useCpuLoads(phase);

  // WebSocket — real-time defects from backend
  useDefectWebSocket(
    (newDefect) => {
      setWsDefects(prev => [newDefect, ...prev].slice(0, 50));
      setDefects(prev => [newDefect, ...prev].slice(0, 100));
      // When WS delivers, we know live is working
      setEverHadLive(true);
    },
    (update: EnrichmentUpdate) => {
      // Track enrichment state
      setEnrichmentMap(prev => {
        const next = new Map(prev);
        next.set(update.defect_id, {
          status: update.status,
          provider: update.provider,
          observation_source: update.observation_source,
          error_message: update.error_message,
          updated_at: update.ts,
        });
        return next;
      });

      // On terminal states: fetch enrichment to get observation/severity_reason
      if (update.status === "complete" || update.status === "rejected" || update.status === "failed") {
        getDefectEnrichment(update.defect_id).then((enr) => {
          if (!enr) return;
          setDefects((prev) =>
            prev.map((d) => {
              if (d.id !== update.defect_id) return d;
              const patch: Partial<DefectRead> = {};
              // On complete: update observation fields from enrichment
              if (update.status === "complete") {
                if (enr.observation) patch.observation = enr.observation;
                if (enr.severity_reason) patch.severity_reason = enr.severity_reason;
                patch.observation_source = update.observation_source ?? enr.provider ?? d.observation_source;
              }
              // On rejected/failed: keep fallback observation if API returns one
              if (update.status === "rejected" || update.status === "failed") {
                if (enr.observation && enr.observation !== d.observation) {
                  patch.observation = enr.observation;
                }
                if (enr.severity_reason && enr.severity_reason !== d.severity_reason) {
                  patch.severity_reason = enr.severity_reason;
                }
              }
              return Object.keys(patch).length > 0 ? { ...d, ...patch } : d;
            }),
          );
        });
      }
      setEverHadLive(true);
    },
  );

  // Unified stats: prefer data source stats, fallback to client-side computed
  const mockStats = useMemo(() => buildStats(defects), [defects]);
  const stats: DashboardStatsLike = apiStats ?? dsStats ?? mockStats;

  const ramUsed = (activeConfig.model_size === "4B" ? 11.4 : 5.0) + (npuLoads[2] / 100) * 0.6;

  const openProfileForDefect = useCallback((d: DefectRead) => {
    const idx = defects.findIndex(x => x.id === d.id);
    setProfileSeedIdx(idx >= 0 ? idx : 0);
    setSelectedDefect(null);
    navigate("profile");
  }, [defects, navigate]);

  return (
    <div style={{ minHeight: "100vh" }}>
      <TopBar now={now} live={dataSourceStatus.kind === "live"} route={route} navigate={navigate} dataSource={dataSourceStatus} />

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
            dataSource={dataSourceStatus}
            manifestCaveats={manifest?.caveats}
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
            <ProfilePage
              defects={defects}
              initialFrameIdx={profileSeedIdx}
              dataSource={dataSourceStatus}
              manifestCaveats={manifest?.caveats}
            />
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
            <ABMatrix
              stats={stats}
              activeConfig={activeConfig}
              dataSource={dataSourceStatus}
              manifestCaveats={manifest?.caveats}
            />
          </>
        )}

        {route === "models" && (
          <ModelsPage activeConfig={activeConfig} onChangeConfig={setActiveConfig} dataSource={dataSourceStatus} />
        )}

        {route === "logs" && (
          <LogsPage dataSource={dataSourceStatus} />
        )}
      </main>

      <BottomBar now={now} live={dataSourceStatus.kind === "live"} route={route} activeConfig={activeConfig} totalDefects={defects.length} dataSource={dataSourceStatus} />

      <DetailDrawer
        defect={selectedDefect}
        onClose={() => setSelectedDefect(null)}
        onOpenProfile={openProfileForDefect}
        enrichment={selectedDefect ? enrichmentMap.get(selectedDefect.id) ?? null : null}
      />
    </div>
  );
}
