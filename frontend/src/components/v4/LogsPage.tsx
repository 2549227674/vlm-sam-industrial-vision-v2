"use client";

import React, { useState, useEffect, useMemo } from "react";
import { fmtTime } from "@/lib/mock-data";
import type { DataSourceStatus } from "@/lib/data-source";
import { DataSourceBadge } from "./DataSourceBadge";

const COMPONENTS = ["EfficientAD", "FastSAM", "Qwen3VL", "Pipeline", "WS", "HTTP"];
const LEVELS = ["INFO", "WARN", "ERROR", "DEBUG"] as const;

const LEVEL_COLOR: Record<string, string> = { INFO: "var(--ok)", WARN: "var(--warn)", ERROR: "var(--crit)", DEBUG: "var(--fg-3)" };
const COMPONENT_COLOR: Record<string, string> = { EfficientAD: "var(--core-0)", FastSAM: "var(--core-1)", Qwen3VL: "var(--core-2)", Pipeline: "var(--acc)", WS: "#7cdcff", HTTP: "#ff9f6c" };

interface LogLine {
  id: string;
  ts: Date;
  level: string;
  component: string;
  msg: string;
}

function makeLogLine(): LogLine {
  const r = Math.random();
  let level = "INFO";
  if (r > 0.95) level = "ERROR";
  else if (r > 0.85) level = "WARN";
  else if (r > 0.78) level = "DEBUG";

  const ts = new Date();
  const variants = ["2B_base", "2B_lora", "4B_base", "4B_lora"];
  const v = variants[Math.floor(Math.random() * variants.length)];

  const lines: [string, string, string][] = [
    ["EfficientAD", "INFO", `anomaly_score=${(Math.random() * 3 + 1).toFixed(2)} · threshold=3.50 → ${Math.random() > 0.6 ? "TRIGGER" : "pass"}`],
    ["FastSAM", "INFO", `bbox_count=${1 + Math.floor(Math.random() * 4)} · mask_area=${(Math.random() * 0.2).toFixed(3)}`],
    ["Qwen3VL", "INFO", `variant=${v} · TTFT=${800 + Math.floor(Math.random() * 1800)}ms · decode=${600 + Math.floor(Math.random() * 900)}ms · tps=${(9 + Math.random() * 4).toFixed(1)}`],
    ["Pipeline", "INFO", `frame F-${Date.now().toString().slice(-5)} complete · total=${2200 + Math.floor(Math.random() * 800)}ms`],
    ["WS", "INFO", `broadcast defect_created → ${1 + Math.floor(Math.random() * 4)} clients`],
    ["HTTP", "INFO", `POST /api/edge/report 200 · ${30 + Math.floor(Math.random() * 80)}ms · multipart`],
    ["Qwen3VL", "WARN", `json partial · retrying with schema hint · variant=${v}`],
    ["Pipeline", "ERROR", "queue depth exceeded (>4) · frame dropped"],
    ["HTTP", "WARN", "retry POST /api/edge/report · backoff 250ms · attempt 2/3"],
    ["EfficientAD", "DEBUG", `rknn ctx ${Math.floor(Math.random() * 4)} · npu0 idle for ${Math.floor(Math.random() * 30)}ms`],
    ["WS", "DEBUG", `ping → pong rtt=${(Math.random() * 8 + 0.5).toFixed(1)}ms · client=dashboard-${Math.floor(Math.random() * 4)}`],
    ["Pipeline", "INFO", `T2 → T3 handoff · queue_len=${Math.floor(Math.random() * 4)}`],
  ];
  const [component, lvl, msg] = lines[Math.floor(Math.random() * lines.length)];
  const finalLevel = level !== "INFO" ? level : lvl;
  return { id: `${ts.getTime()}-${Math.random().toString(16).slice(2, 6)}`, ts, level: finalLevel, component, msg };
}

function seedLogs(n = 40): LogLine[] {
  const out: LogLine[] = [];
  for (let i = 0; i < n; i++) {
    const l = makeLogLine();
    l.ts = new Date(Date.now() - (n - i) * 1200 - Math.random() * 800);
    out.push(l);
  }
  return out;
}

export function LogsPage({ accent = "var(--acc)", dataSource }: { accent?: string; dataSource?: DataSourceStatus }) {
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [paused, setPaused] = useState(false);
  const [filterLevel, setFilterLevel] = useState("ALL");
  const [filterComp, setFilterComp] = useState("ALL");
  const [search, setSearch] = useState("");

  useEffect(() => { setLogs(seedLogs(60)); }, []);

  useEffect(() => {
    if (paused) return;
    const id = setInterval(() => {
      setLogs(prev => {
        const burst = 1 + Math.floor(Math.random() * 3);
        const next: LogLine[] = [];
        for (let i = 0; i < burst; i++) next.push(makeLogLine());
        return [...next, ...prev].slice(0, 200);
      });
    }, 900);
    return () => clearInterval(id);
  }, [paused]);

  const filtered = useMemo(() => {
    return logs.filter(l => {
      if (filterLevel !== "ALL" && l.level !== filterLevel) return false;
      if (filterComp !== "ALL" && l.component !== filterComp) return false;
      if (search && !l.msg.toLowerCase().includes(search.toLowerCase()) && !l.component.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [logs, filterLevel, filterComp, search]);

  const lastTs = logs[0]?.ts ?? new Date();
  const eventRate = logs.length > 0 ? (logs.filter(l => (Date.now() - l.ts.getTime()) < 10000).length / 10).toFixed(1) : "0.0";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ paddingTop: 8 }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "4px 12px", border: "1px solid var(--line)", borderRadius: 100, marginBottom: 18 }}>
          <span style={{ width: 6, height: 6, background: accent, borderRadius: "50%", boxShadow: `0 0 6px ${accent}` }} />
          <span className="mono" style={{ fontSize: 10, color: "var(--fg-2)", letterSpacing: "0.1em" }}>日志 · 实时事件流</span>
        </div>
        <h1 style={{ margin: 0, fontSize: 44, fontWeight: 600, lineHeight: 1.05, letterSpacing: "-0.025em" }}>
          边缘日志尾，
          <span style={{ display: "block", color: "var(--fg-3)" }}>横跨 <span style={{ color: accent }}>6 个组件</span>。</span>
        </h1>
      </div>

      {/* Status rail */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 1, background: "var(--line)", border: "1px solid var(--line)" }}>
        {[
          { l: "数据来源", v: dataSource?.label ?? "Mock", c: dataSource?.color ?? "var(--warn)", dot: true, badge: true },
          { l: "WS 客户端", v: "2 已连接", c: "var(--fg)" },
          { l: "最近事件", v: fmtTime(lastTs), c: "var(--fg)" },
          { l: "事件速率", v: `${eventRate} /s`, c: "var(--fg)" },
        ].map(s => (
          <div key={s.l} style={{ background: "var(--bg-1)", padding: "12px 16px" }}>
            <div className="eyebrow" style={{ fontSize: 9 }}>{s.l}</div>
            <div style={{ display: "flex", alignItems: "center", gap: 7, marginTop: 4 }}>
              {s.dot && <span style={{ width: 7, height: 7, background: s.c, borderRadius: "50%", boxShadow: `0 0 6px ${s.c}` }} />}
              <span className="mono" style={{ fontSize: 14, color: s.c, fontWeight: 500, letterSpacing: "0.02em" }}>{s.v}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Filter bar */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center", padding: "10px 14px", border: "1px solid var(--line)", background: "var(--bg-1)" }}>
        <SegBar value={filterLevel} onChange={setFilterLevel} options={[["ALL", "全部"], ...LEVELS.map((l): [string, string] => [l, l])]} />
        <span style={{ width: 1, height: 20, background: "var(--line)" }} />
        <SegBar value={filterComp} onChange={setFilterComp} options={[["ALL", "全部"], ...COMPONENTS.map((c): [string, string] => [c, c])]} compact />
        <span style={{ flex: 1 }} />
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="搜索消息…" style={{ background: "var(--bg-2)", border: "1px solid var(--line)", color: "var(--fg)", padding: "5px 10px", fontFamily: "var(--font-mono)", fontSize: 12, width: 220, outline: "none" }} />
        <button onClick={() => setPaused(p => !p)} style={{
          background: paused ? "var(--warn)" : "transparent",
          color: paused ? "var(--bg)" : "var(--fg-2)",
          border: `1px solid ${paused ? "var(--warn)" : "var(--line)"}`,
          padding: "5px 12px", fontFamily: "var(--font-mono)", fontSize: 11,
          letterSpacing: "0.1em", fontWeight: 600, textTransform: "uppercase", cursor: "pointer",
        }}>{paused ? "▶ 继续" : "❚❚ 暂停"}</button>
      </div>

      {/* Terminal */}
      <div style={{ background: "#08080c", border: "1px solid var(--line)", height: 540, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        <div style={{ padding: "6px 12px", borderBottom: "1px solid var(--line)", background: "var(--bg-2)", display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#ff6378" }} />
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#ffbf5c" }} />
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#6dffac" }} />
          <span className="mono" style={{ marginLeft: 10, fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.12em" }}>edge@rk3588:~ · tail -f /var/log/edge/dashboard.log · {filtered.length} 条匹配</span>
          <span style={{ flex: 1 }} />
          {!paused && (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 6, height: 6, background: "var(--ok)", borderRadius: "50%", boxShadow: "0 0 4px var(--ok)", animation: "pulse-dot 1.4s infinite" }} />
              <span className="mono" style={{ fontSize: 9, color: "var(--ok)", letterSpacing: "0.12em" }}>实时流</span>
            </span>
          )}
        </div>
        <div style={{ flex: 1, overflowY: "auto" }}>
          {filtered.slice(0, 120).map(l => {
            const lc = LEVEL_COLOR[l.level] || "var(--fg-2)";
            const cc = COMPONENT_COLOR[l.component] || "var(--fg-2)";
            return (
              <div key={l.id} style={{ display: "grid", gridTemplateColumns: "90px 56px 110px 1fr", gap: 12, padding: "5px 14px", borderBottom: "1px solid var(--line-soft)", fontFamily: "var(--font-mono)", fontSize: 11, lineHeight: 1.5, animation: "log-in 0.18s ease-out" }}>
                <span style={{ color: "var(--fg-3)" }}>{fmtTime(l.ts)}</span>
                <span style={{ padding: "0 5px", color: lc, border: `1px solid ${lc}`, background: `color-mix(in srgb, ${lc} 12%, transparent)`, fontSize: 9, fontWeight: 700, letterSpacing: "0.06em", display: "inline-flex", alignItems: "center", justifyContent: "center", height: 16, alignSelf: "center" }}>{l.level}</span>
                <span style={{ color: cc, fontWeight: 600 }}>[{l.component}]</span>
                <span style={{ color: "var(--fg-1)", wordBreak: "break-word" }}>{l.msg}</span>
              </div>
            );
          })}
          {!filtered.length && (
            <div style={{ padding: 40, textAlign: "center", color: "var(--fg-4)", fontFamily: "var(--font-mono)", fontSize: 12 }}>无匹配事件。</div>
          )}
        </div>
      </div>
    </div>
  );
}

function SegBar({ value, onChange, options, compact }: { value: string; onChange: (v: string) => void; options: [string, string][]; compact?: boolean }) {
  return (
    <div style={{ display: "inline-flex", border: "1px solid var(--line)" }}>
      {options.map(([v, l], i) => {
        const active = value === v;
        return (
          <button key={v} onClick={() => onChange(v)} style={{
            padding: compact ? "4px 9px" : "5px 11px",
            fontFamily: "var(--font-mono)", fontSize: compact ? 10 : 11, letterSpacing: "0.08em",
            fontWeight: 600, background: active ? "var(--acc)" : "transparent",
            color: active ? "var(--bg)" : "var(--fg-2)", border: "none",
            borderRight: i < options.length - 1 ? "1px solid var(--line)" : "none", cursor: "pointer",
          }}>{l}</button>
        );
      })}
    </div>
  );
}
