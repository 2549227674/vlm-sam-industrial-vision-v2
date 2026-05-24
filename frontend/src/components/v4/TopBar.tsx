"use client";

import React from "react";
import { fmtTime } from "@/lib/mock-data";
import type { DataSourceStatus } from "@/lib/data-source";
import { DataSourceBadge } from "./DataSourceBadge";

interface TopBarProps {
  now: Date | null;
  live: boolean;
  route: string;
  navigate?: (key: string) => void;
  accent?: string;
  dataSource?: DataSourceStatus;
}

export function TopBar({ now, live, route, accent = "var(--acc)", dataSource }: TopBarProps) {
  const navItems = [
    { key: "overview", label: "总览" },
    { key: "profile", label: "性能剖析" },
    { key: "ab", label: "变体对比" },
    { key: "models", label: "模型" },
    { key: "logs", label: "日志" },
  ];

  return (
    <header
      style={{
        padding: "18px 32px", maxWidth: 1480, margin: "0 auto",
        display: "flex", justifyContent: "space-between", alignItems: "center", gap: 24,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <Logo accent={accent} />
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, letterSpacing: "-0.01em" }}>
            边缘视觉 <span style={{ color: "var(--fg-3)", fontWeight: 400 }}>· RK3588 数字孪生</span>
          </div>
          <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginTop: 1 }}>
            v1.1.0 · mvtec-ad · qwen3-vl-2b/4b · w8a8
          </div>
        </div>
      </div>

      <nav style={{ display: "flex", gap: 24 }}>
        {navItems.map((item) => {
          const active = route === item.key;
          return (
            <a
              key={item.key}
              href={`#${item.key}`}
              style={{
                color: active ? "var(--fg)" : "var(--fg-2)",
                fontSize: 13, fontWeight: 500, textDecoration: "none",
                paddingBottom: 2, borderBottom: active ? `1px solid ${accent}` : "1px solid transparent",
              }}
            >
              {item.label}
            </a>
          );
        })}
      </nav>

      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        {dataSource ? (
          <DataSourceBadge status={dataSource} />
        ) : (
          <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span
              style={{
                width: 7, height: 7, background: live ? "var(--ok)" : "var(--warn)",
                borderRadius: "50%", boxShadow: `0 0 6px ${live ? "var(--ok)" : "var(--warn)"}`,
                animation: live ? "pulse-dot 1.4s infinite" : "none",
              }}
            />
            <span className="mono" style={{ fontSize: 11, color: live ? "var(--ok)" : "var(--warn)" }}>
              {live ? "实时" : "已暂停"}
            </span>
          </span>
        )}
        <span className="mono" style={{ fontSize: 11, color: "var(--fg-2)" }} suppressHydrationWarning>{now ? fmtTime(now) : "—"}</span>
      </div>
    </header>
  );
}

function Logo({ accent }: { accent: string }) {
  return (
    <div style={{ width: 28, height: 28, position: "relative" }}>
      <div style={{ position: "absolute", inset: 0, border: `1px solid ${accent}`, transform: "rotate(45deg)" }} />
      <div style={{ position: "absolute", inset: 5, background: accent, opacity: 0.4, transform: "rotate(45deg)" }} />
      <div style={{ position: "absolute", inset: 10, background: accent, transform: "rotate(45deg)" }} />
    </div>
  );
}
