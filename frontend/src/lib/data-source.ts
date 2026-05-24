/**
 * data-source.ts — Multi-source data resolution for the dashboard.
 *
 * Priority: Live API > Real RK3588 Snapshot > Mock Fallback
 *
 * The snapshot lives in /demo-data/real_run_latest/ and was exported from a
 * real RK3588 threshold soak test (Phase 9, 2026-05-24).  It is NOT a live
 * stream — it is a static historical recording.
 */

import { useState, useEffect, useCallback, useRef } from "react";
import type { DefectRead } from "@/types/defect";
import type { DashboardStatsLike, StatsResponse } from "@/types/stats";
import { seedDefects, buildStats } from "@/lib/mock-data";
import { API_BASE } from "@/lib/api";

// ── Status types ─────────────────────────────────────────────────────────────

export type DataSourceKind = "live" | "snapshot" | "mock" | "reconnecting";

export interface DataSourceStatus {
  kind: DataSourceKind;
  label: string;
  labelEn: string;
  color: string;
  description: string;
  lastEventAt?: string;
  attempt?: number;
}

export const DATA_SOURCE_PRESETS: Record<DataSourceKind, DataSourceStatus> = {
  live: {
    kind: "live",
    label: "实时 RK3588 API",
    labelEn: "Live RK3588 API",
    color: "var(--ok)",
    description: "已连接实时后端，数据来自 RK3588 边缘流水线。 / Connected to live backend. Data is from real-time RK3588 edge pipeline.",
  },
  snapshot: {
    kind: "snapshot",
    label: "真实 RK3588 快照",
    labelEn: "Real RK3588 Snapshot",
    color: "#7cdcff",
    description: "展示历史真实 RK3588 测试数据，非实时流。 / Showing historical real RK3588 test data. Not a live stream.",
  },
  mock: {
    kind: "mock",
    label: "Mock 演示数据",
    labelEn: "Mock Fallback",
    color: "var(--warn)",
    description: "后端不可达，使用合成 mock 数据，仅供演示。 / Backend unreachable. Using synthetic mock data for demo purposes only.",
  },
  reconnecting: {
    kind: "reconnecting",
    label: "WebSocket 重连中",
    labelEn: "Reconnecting",
    color: "var(--warn)",
    description: "WebSocket 连接断开，正在重连。 / WebSocket connection lost. Attempting to reconnect to live backend.",
  },
};

// ── Snapshot manifest type ───────────────────────────────────────────────────

export interface SnapshotManifest {
  schema: string;
  source: string;
  run_id: string;
  created_at: string;
  is_mock: boolean;
  is_live: boolean;
  mode: string;
  duration_min: number;
  edge_device: string;
  contract_version: string;
  mainline: Record<string, string>;
  data_counts: {
    records: number;
    images: number;
    categories: string[];
    variants: string[];
  };
  data_source_label: string;
  caveats: string[];
  release_gate: Record<string, unknown>;
}

// ── Hook: useDataSource ──────────────────────────────────────────────────────

export interface UseDataSourceResult {
  defects: DefectRead[];
  stats: DashboardStatsLike;
  status: DataSourceStatus;
  manifest: SnapshotManifest | null;
  refresh: () => void;
}

/**
 * Snapshot defect items use the same contract schema but may lack `id` and
 * `server_ts` which are backend-assigned.  We normalise them here.
 */
function normaliseSnapshotDefects(items: DefectRead[]): DefectRead[] {
  return items.map((d, i) => ({
    ...d,
    id: d.id ?? 100000 + i,
    server_ts: d.server_ts ?? d.edge_ts,
    schema_version: (d.schema_version ?? "v1") as "v1",
  }));
}

function normaliseSnapshotStats(raw: Record<string, unknown>): StatsResponse {
  return {
    total: (raw.total as number) ?? 0,
    today_defects: (raw.total as number) ?? 0,
    today_high: (raw.by_severity as Record<string, number>)?.high ?? 0,
    by_category: (raw.by_category as Record<string, number>) ?? {},
    by_severity: (raw.by_severity as Record<string, number>) ?? {},
    ab_compare: (raw.ab_compare as StatsResponse["ab_compare"]) ?? {},
    timeline: [],
    avg_pipeline_ms: (raw.avg_pipeline_ms as StatsResponse["avg_pipeline_ms"]) ?? { efficientad: 0, fastsam: 0, qwen3vl: 0 },
    category_severity_matrix: (raw.category_severity_matrix as StatsResponse["category_severity_matrix"]) ?? {},
  };
}

export function useDataSource(): UseDataSourceResult {
  const [defects, setDefects] = useState<DefectRead[]>([]);
  const [stats, setStats] = useState<DashboardStatsLike>(buildStats([]));
  const [status, setStatus] = useState<DataSourceStatus>(DATA_SOURCE_PRESETS.mock);
  const [manifest, setManifest] = useState<SnapshotManifest | null>(null);
  const refreshRef = useRef(0);

  const load = useCallback(async () => {
    const runId = ++refreshRef.current;

    // ── Try 1: Live API ────────────────────────────────────────────────────
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 5000);

      const [defectsResp, statsResp] = await Promise.all([
        fetch(`${API_BASE}/api/defects?page=1&page_size=100&sort=-edge_ts`, { signal: controller.signal }),
        fetch(`${API_BASE}/api/stats`, { signal: controller.signal }),
      ]);
      clearTimeout(timeout);

      if (defectsResp.ok && statsResp.ok) {
        if (runId !== refreshRef.current) return;
        const defectsData = await defectsResp.json();
        const statsData = await statsResp.json();

        setDefects(defectsData.items ?? []);
        setStats(statsData as StatsResponse);
        setStatus({ ...DATA_SOURCE_PRESETS.live, lastEventAt: new Date().toISOString() });
        setManifest(null);
        return;
      }
    } catch {
      // Live API unreachable — fall through to snapshot
    }

    // ── Try 2: Real RK3588 Snapshot ────────────────────────────────────────
    try {
      const [manifestResp, defectsResp, statsResp] = await Promise.all([
        fetch("/demo-data/real_run_latest/manifest.json", { signal: AbortSignal.timeout(3000) }),
        fetch("/demo-data/real_run_latest/defects_snapshot.json", { signal: AbortSignal.timeout(3000) }),
        fetch("/demo-data/real_run_latest/stats_snapshot.json", { signal: AbortSignal.timeout(3000) }),
      ]);

      if (manifestResp.ok && defectsResp.ok && statsResp.ok) {
        if (runId !== refreshRef.current) return;
        const manifestData: SnapshotManifest = await manifestResp.json();
        const defectsData = await defectsResp.json();
        const statsData = await statsResp.json();

        setDefects(normaliseSnapshotDefects(defectsData.items ?? []));
        setStats(normaliseSnapshotStats(statsData));
        setStatus({
          ...DATA_SOURCE_PRESETS.snapshot,
          lastEventAt: manifestData.created_at,
        });
        setManifest(manifestData);
        return;
      }
    } catch {
      // Snapshot files missing — fall through to mock
    }

    // ── Try 3: Mock Fallback ───────────────────────────────────────────────
    if (runId !== refreshRef.current) return;
    setDefects(seedDefects(80));
    setStats(buildStats(seedDefects(80)));
    setStatus(DATA_SOURCE_PRESETS.mock);
    setManifest(null);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { defects, stats, status, manifest, refresh: load };
}
