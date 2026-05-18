// V4 Logs page — terminal-style live event stream.

const { useState: _lgS, useEffect: _lgE, useMemo: _lgM, useRef: _lgR } = React;

const COMPONENTS = ["EfficientAD", "FastSAM", "Qwen3VL", "Pipeline", "WS", "HTTP"];
const LEVELS = ["INFO", "WARN", "ERROR", "DEBUG"];

const LEVEL_COLOR = {
  INFO:  "var(--ok)",
  WARN:  "var(--warn)",
  ERROR: "var(--crit)",
  DEBUG: "var(--fg-3)",
};

const COMPONENT_COLOR = {
  EfficientAD: "var(--core-0)",
  FastSAM:     "var(--core-1)",
  Qwen3VL:     "var(--core-2)",
  Pipeline:    "var(--acc)",
  WS:          "#7cdcff",
  HTTP:        "#ff9f6c",
};

// Templated event factory — produces plausible structured log lines.
function makeLogLine(){
  const r = Math.random();
  let level = "INFO";
  if (r > 0.95) level = "ERROR";
  else if (r > 0.85) level = "WARN";
  else if (r > 0.78) level = "DEBUG";

  const ts = new Date();
  const variants = window.VARIANTS || ["2B_base","2B_lora","4B_base","4B_lora"];
  const v = variants[Math.floor(Math.random() * variants.length)];

  const lines = [
    () => ["EfficientAD", "INFO",  `anomaly_score=${(Math.random()*3+1).toFixed(2)} · threshold=3.50 → ${Math.random() > 0.6 ? "TRIGGER" : "pass"}`],
    () => ["FastSAM",     "INFO",  `bbox_count=${1 + Math.floor(Math.random()*4)} · mask_area=${(Math.random()*0.2).toFixed(3)}`],
    () => ["Qwen3VL",     "INFO",  `variant=${v} · TTFT=${800 + Math.floor(Math.random()*1800)}ms · decode=${600 + Math.floor(Math.random()*900)}ms · tps=${(9 + Math.random()*4).toFixed(1)}`],
    () => ["Pipeline",    "INFO",  `frame F-${Date.now().toString().slice(-5)} complete · total=${2200 + Math.floor(Math.random()*800)}ms`],
    () => ["WS",          "INFO",  `broadcast defect_created → ${1 + Math.floor(Math.random()*4)} clients`],
    () => ["HTTP",        "INFO",  `POST /api/edge/report 200 · ${30 + Math.floor(Math.random()*80)}ms · multipart`],
    () => ["Qwen3VL",     "WARN",  `json partial · retrying with schema hint · variant=${v}`],
    () => ["Pipeline",    "ERROR", `queue depth exceeded (>4) · frame dropped`],
    () => ["HTTP",        "WARN",  `retry POST /api/edge/report · backoff 250ms · attempt 2/3`],
    () => ["EfficientAD", "DEBUG", `rknn ctx ${Math.floor(Math.random()*4)} · npu0 idle for ${Math.floor(Math.random()*30)}ms`],
    () => ["WS",          "DEBUG", `ping → pong rtt=${(Math.random()*8 + 0.5).toFixed(1)}ms · client=dashboard-${Math.floor(Math.random()*4)}`],
    () => ["Pipeline",    "INFO",  `T2 → T3 handoff · queue_len=${Math.floor(Math.random()*4)}`],
  ];
  let [component, lvl, msg] = lines[Math.floor(Math.random() * lines.length)]();
  if (level !== "INFO") lvl = level;
  return { id: `${ts.getTime()}-${Math.random().toString(16).slice(2,6)}`, ts, level: lvl, component, msg };
}

function seedLogs(n = 40){
  const out = [];
  for (let i = 0; i < n; i++){
    const l = makeLogLine();
    l.ts = new Date(Date.now() - (n - i) * 1200 - Math.random() * 800);
    out.push(l);
  }
  return out;
}

function LogsPage({ accent = "var(--acc)" }){
  const [logs, setLogs] = _lgS(() => seedLogs(60));
  const [paused, setPaused] = _lgS(false);
  const [filterLevel, setFilterLevel] = _lgS("ALL");
  const [filterComp,  setFilterComp]  = _lgS("ALL");
  const [search, setSearch] = _lgS("");

  _lgE(() => {
    if (paused) return;
    const id = setInterval(() => {
      setLogs(prev => {
        const burst = 1 + Math.floor(Math.random() * 3);
        const next = [];
        for (let i = 0; i < burst; i++) next.push(makeLogLine());
        return [...next, ...prev].slice(0, 200);
      });
    }, 900);
    return () => clearInterval(id);
  }, [paused]);

  const filtered = _lgM(() => {
    return logs.filter(l => {
      if (filterLevel !== "ALL" && l.level !== filterLevel) return false;
      if (filterComp  !== "ALL" && l.component !== filterComp) return false;
      if (search && !l.msg.toLowerCase().includes(search.toLowerCase()) && !l.component.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [logs, filterLevel, filterComp, search]);

  // status rail values
  const lastTs = logs[0]?.ts ?? new Date();
  const eventRate = (logs.filter(l => (Date.now() - l.ts.getTime()) < 10000).length / 10).toFixed(1);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Hero */}
      <div style={{ paddingTop: 8 }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "4px 12px",
                      border: "1px solid var(--line)", borderRadius: 100, marginBottom: 18 }}>
          <span style={{ width: 6, height: 6, background: accent, borderRadius: "50%", boxShadow: `0 0 6px ${accent}` }} />
          <span className="mono" style={{ fontSize: 10, color: "var(--fg-2)", letterSpacing: "0.1em" }}>日志 · 实时事件流</span>
        </div>
        <h1 style={{ margin: 0, fontSize: 44, fontWeight: 600, lineHeight: 1.05, letterSpacing: "-0.025em" }}>
          边缘日志尾，
          <span style={{ display: "block", color: "var(--fg-3)" }}>
            横跨 <span style={{ color: accent }}>6 个组件</span>。
          </span>
        </h1>
      </div>

      {/* Status rail */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 1,
                    background: "var(--line)", border: "1px solid var(--line)" }}>
        <StatusTile label="后端"  value="健康"  c="var(--ok)"  dot />
        <StatusTile label="WS 客户端"    value="2 已连接" c="var(--fg)" />
        <StatusTile label="最近事件"    value={fmtTime(lastTs)} c="var(--fg)" />
        <StatusTile label="事件速率"    value={`${eventRate} /s`} c="var(--fg)" />
      </div>

      {/* Filter bar */}
      <div style={{
        display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center",
        padding: "10px 14px", border: "1px solid var(--line)", background: "var(--bg-1)",
      }}>
        <SegBar value={filterLevel} onChange={setFilterLevel}
                options={[["ALL","全部"],...LEVELS.map(l => [l, l])]} />
        <span style={{ width: 1, height: 20, background: "var(--line)" }} />
        <SegBar value={filterComp} onChange={setFilterComp}
                options={[["ALL","全部"],...COMPONENTS.map(c => [c, c])]} compact />
        <span style={{ flex: 1 }} />
        <input value={search} onChange={e => setSearch(e.target.value)}
               placeholder="搜索消息…"
               style={{
                 background: "var(--bg-2)", border: "1px solid var(--line)",
                 color: "var(--fg)", padding: "5px 10px",
                 fontFamily: "var(--font-mono)", fontSize: 12,
                 width: 220, outline: "none",
               }} />
        <button onClick={() => setPaused(p => !p)} style={{
          background: paused ? "var(--warn)" : "transparent",
          color: paused ? "var(--bg)" : "var(--fg-2)",
          border: `1px solid ${paused ? "var(--warn)" : "var(--line)"}`,
          padding: "5px 12px", fontFamily: "var(--font-mono)", fontSize: 11,
          letterSpacing: "0.1em", fontWeight: 600, textTransform: "uppercase",
          cursor: "pointer",
        }}>{paused ? "▶ 继续" : "❚❚ 暂停"}</button>
      </div>

      {/* Terminal */}
      <div style={{
        background: "#08080c", border: "1px solid var(--line)",
        height: 540, overflow: "hidden",
        display: "flex", flexDirection: "column",
      }}>
        {/* Terminal header */}
        <div style={{
          padding: "6px 12px", borderBottom: "1px solid var(--line)",
          background: "var(--bg-2)",
          display: "flex", alignItems: "center", gap: 6,
        }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#ff6378" }} />
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#ffbf5c" }} />
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#6dffac" }} />
          <span className="mono" style={{
            marginLeft: 10, fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.12em",
          }}>edge@rk3588:~ · tail -f /var/log/edge/dashboard.log · {filtered.length} 条匹配</span>
          <span style={{ flex: 1 }} />
          {!paused && (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <span style={{
                width: 6, height: 6, background: "var(--ok)",
                borderRadius: "50%", boxShadow: "0 0 4px var(--ok)",
                animation: "pulse-dot 1.4s infinite",
              }} />
              <span className="mono" style={{ fontSize: 9, color: "var(--ok)", letterSpacing: "0.12em" }}>实时流</span>
            </span>
          )}
        </div>

        {/* Log rows */}
        <div style={{ flex: 1, overflowY: "auto" }}>
          {filtered.slice(0, 120).map(l => (
            <LogRow key={l.id} log={l} />
          ))}
          {!filtered.length && (
            <div style={{ padding: 40, textAlign: "center", color: "var(--fg-4)", fontFamily: "var(--font-mono)", fontSize: 12 }}>
              无匹配事件。
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatusTile({ label, value, c = "var(--fg)", dot }){
  return (
    <div style={{ background: "var(--bg-1)", padding: "12px 16px" }}>
      <div className="eyebrow" style={{ fontSize: 9 }}>{label}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 7, marginTop: 4 }}>
        {dot && <span style={{ width: 7, height: 7, background: c, borderRadius: "50%", boxShadow: `0 0 6px ${c}` }} />}
        <span className="mono" style={{ fontSize: 14, color: c, fontWeight: 500, letterSpacing: "0.02em" }}>{value}</span>
      </div>
    </div>
  );
}

function SegBar({ value, onChange, options, compact }){
  return (
    <div style={{ display: "inline-flex", border: "1px solid var(--line)" }}>
      {options.map(([v, l], i) => {
        const active = value === v;
        return (
          <button key={v} onClick={() => onChange(v)} style={{
            padding: compact ? "4px 9px" : "5px 11px",
            fontFamily: "var(--font-mono)", fontSize: compact ? 10 : 11, letterSpacing: "0.08em",
            fontWeight: 600,
            background: active ? "var(--acc)" : "transparent",
            color: active ? "var(--bg)" : "var(--fg-2)",
            border: "none",
            borderRight: i < options.length - 1 ? "1px solid var(--line)" : "none",
            cursor: "pointer",
          }}>{l}</button>
        );
      })}
    </div>
  );
}

function LogRow({ log }){
  const lc = LEVEL_COLOR[log.level] || "var(--fg-2)";
  const cc = COMPONENT_COLOR[log.component] || "var(--fg-2)";
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "90px 56px 110px 1fr",
      gap: 12, padding: "5px 14px",
      borderBottom: "1px solid var(--line-soft)",
      fontFamily: "var(--font-mono)", fontSize: 11, lineHeight: 1.5,
      animation: "log-in 0.18s ease-out",
    }}>
      <span style={{ color: "var(--fg-3)" }}>{fmtTime(log.ts)}</span>
      <span style={{
        padding: "0 5px", color: lc,
        border: `1px solid ${lc}`,
        background: `color-mix(in srgb, ${lc} 12%, transparent)`,
        fontSize: 9, fontWeight: 700, letterSpacing: "0.06em",
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        height: 16, alignSelf: "center",
      }}>{log.level}</span>
      <span style={{ color: cc, fontWeight: 600 }}>[{log.component}]</span>
      <span style={{ color: "var(--fg-1)", wordBreak: "break-word" }}>{log.msg}</span>
    </div>
  );
}

Object.assign(window, { LogsPage });
