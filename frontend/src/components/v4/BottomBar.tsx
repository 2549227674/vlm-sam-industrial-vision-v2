"use client";

import React from "react";
import { fmtDateTime } from "@/lib/mock-data";
import type { ActiveConfig } from "@/types/defect";
import type { DataSourceStatus } from "@/lib/data-source";

interface BottomBarProps {
  now: Date | null;
  live: boolean;
  route: string;
  activeConfig: ActiveConfig;
  totalDefects: number;
  dataSource?: DataSourceStatus;
}

export function BottomBar({ now, live, route, activeConfig, totalDefects, dataSource }: BottomBarProps) {
  return (
    <footer
      style={{
        borderTop: "1px solid var(--line-soft)",
        maxWidth: 1480, margin: "40px auto 0", padding: "20px 32px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        color: "var(--fg-3)", fontFamily: "var(--font-mono)", fontSize: 10,
        flexWrap: "wrap", gap: 12,
      }}
    >
      <div style={{ display: "flex", gap: 18, flexWrap: "wrap" }}>
        <span style={{ color: dataSource?.color }}>● {dataSource?.label ?? (live ? "Live" : "Paused")}</span>
        <span>WS /ws/dashboard {live ? "已连接" : "已暂停"}</span>
        <span>schema v1.1</span>
        <span>vision.db · WAL</span>
        <span>路由 · #{route}</span>
        <span>事件数 n={totalDefects}</span>
        <span>变体 · {activeConfig.model_size}_{activeConfig.variant}</span>
      </div>
      <div>build 2026.05.24 · UTC+8 · {now ? fmtDateTime(now) : "—"}</div>
    </footer>
  );
}
