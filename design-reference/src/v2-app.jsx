// V2 main app — Mission Control / Profiler dashboard.

const { useState: _appS, useEffect: _appE, useMemo: _appM, useRef: _appR } = React;

function App(){
  const t = (window.useTweaks || (() => [{}, () => {}]))(window.__TWEAK_DEFAULTS__V2 || {});
  const [tweaks, setTweak] = t;
  const live = tweaks.live !== false;

  const [defects, setDefects] = _appS(() => seedDefects(140));
  const [selected, setSelected] = _appS(null);
  const [tick, setTick] = _appS(0);
  const [now, setNow] = _appS(new Date());

  // Live event simulation
  _appE(() => {
    if (!live) return;
    let cancelled = false;
    function loop(){
      if (cancelled) return;
      const d = makeDefect({ ts: new Date() });
      d._new = true;
      setDefects(prev => [d, ...prev].slice(0, 240));
      setTick(t => t + 1);
      setTimeout(loop, 2500 + Math.random() * 4000);
    }
    const id = setTimeout(loop, 2200);
    return () => { cancelled = true; clearTimeout(id); };
  }, [live]);

  // Clock + NPU sample tick
  _appE(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const stats = _appM(() => buildStats(defects), [defects]);
  const timeline = _appM(() => buildTimeline(defects), [defects]);
  const recent = _appM(() => defects.slice(0, 40), [defects]);

  const avgTotal = recent.length
    ? recent.reduce((s, d) => s + d.pipeline_ms.efficientad + d.pipeline_ms.fastsam + d.pipeline_ms.qwen3vl, 0) / recent.length
    : 0;
  const fps = avgTotal > 0 ? (1000 / avgTotal) : 0;
  const qps = (defects.filter(d => Date.now() - d.edge_ts.getTime() < 60_000).length / 60).toFixed(2);

  return (
    <div style={{
      minHeight: "100vh", background: "var(--bg-0)",
      display: "flex", flexDirection: "column",
    }}>
      {/* Top bar */}
      <TopBar now={now} live={live} qps={qps} fps={fps} stats={stats} />

      {/* Main grid */}
      <div style={{
        display: "grid",
        gridTemplateColumns: selected ? "minmax(0,1fr) 460px" : "1fr",
        gap: 1, background: "var(--line)",
        flex: 1, padding: 1,
      }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 1, background: "var(--line)", minWidth: 0 }}>
          {/* KPI strip */}
          <KPIStrip stats={stats} avgTotal={avgTotal} fps={fps} tick={tick} />

          {/* Hero — pipeline waterfall */}
          <Panel id="P-001" eyebrow="HERO" title="3-Stage Pipeline · Per-frame Latency Waterfall"
                 hot="var(--sig-cyan)" padded={false}
                 right={<>
                   <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>last <span style={{ color: "var(--fg-1)" }}>{Math.min(20, recent.length)}</span> frames</span>
                   <StatusDot state="online" />
                 </>}
                 footer={<>
                   <span>profiler · libnsys-style render</span>
                   <span>FPS = 1000 / Σpipeline = <span style={{ color: "var(--sig-cyan)" }}>{fps.toFixed(2)}</span></span>
                 </>}>
            <div style={{ padding: "14px 14px 0" }}>
              <PipelineWaterfall samples={recent.slice(0, 20)} height={290} />
            </div>
          </Panel>

          {/* Two column: NPU + Severity matrix */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "var(--line)" }}>
            <Panel id="P-002" eyebrow="HARDWARE" title="RK3588 NPU · Real-time Utilization"
                   right={<INT8Badge />}
                   footer={<><span>polled @ 2 Hz</span><span>tick #{tick}</span></>}>
              <NPUUtilization frames={recent} qps={qps} />
            </Panel>
            <Panel id="P-003" eyebrow="DISTRIBUTION" title="Defects by Category × Severity"
                   right={<span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>n = {stats.total}</span>}
                   footer={<><span>aggregate · last 24h</span><span>updated {fmtTime(now)}</span></>}>
              <CategorySeverityMatrix stats={stats} />
            </Panel>
          </div>

          {/* Throughput */}
          <Panel id="P-004" eyebrow="THROUGHPUT" title="Frame Volume · 24h Histogram"
                 right={<span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>
                   bucket = 1h · cyan = total · red = high-severity overlay
                 </span>}
                 footer={<><span>edge_ts based · server time-zone local</span><span>n = {stats.total}</span></>}>
            <ThroughputChart buckets={timeline} height={150} />
          </Panel>

          {/* AB Compare */}
          <Panel id="P-005" eyebrow="AB EXPERIMENT" title="LoRA finetune vs Base+Long-Prompt · 5-axis"
                 hot="var(--sig-teal)" padded={false}
                 right={<>
                   <button onClick={() => setTweak("abFocus", "ttft")}
                     style={focusBtn(tweaks.abFocus === "ttft")}>TTFT</button>
                   <button onClick={() => setTweak("abFocus", "json")}
                     style={focusBtn(tweaks.abFocus === "json")}>JSON</button>
                   <button onClick={() => setTweak("abFocus", "rss")}
                     style={focusBtn(tweaks.abFocus === "rss")}>RSS</button>
                 </>}
                 footer={<><span>backed by /api/stats · ab_compare</span><span>same MVTec test split</span></>}>
            <ABCompare stats={stats} focus={tweaks.abFocus || "ttft"} />
          </Panel>

          {/* Live stream */}
          <Panel id="P-006" eyebrow="STREAM" title="Live Defect Feed · WebSocket"
                 padded={false}
                 right={<>
                   <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>QPS <span style={{ color: "var(--sig-cyan)" }}>{qps}</span></span>
                   <StatusDot state={live ? "online" : "stale"} />
                 </>}
                 footer={<><span>click row to open inspector</span><span>show {Math.min(14, defects.length)} of {defects.length}</span></>}>
            <LiveStream defects={defects} onSelect={setSelected} selectedId={selected?.id} />
          </Panel>
        </div>

        {selected && (
          <DetailDrawer defect={selected} onClose={() => setSelected(null)} />
        )}
      </div>

      <BottomStatus now={now} stats={stats} qps={qps} live={live} tick={tick} />

      {window.TweaksPanel && (
        <TweaksPanel title="Tweaks" defaults={window.__TWEAK_DEFAULTS__V2 || {}}>
          {(t, set) => (
            <>
              <TweakSection title="Display">
                <TweakRadio label="AB focus axis" value={t.abFocus || "ttft"}
                  onChange={v => set("abFocus", v)}
                  options={[["ttft","TTFT"],["json","JSON"],["rss","RSS"]]} />
                <TweakToggle label="Live stream" value={t.live !== false}
                  onChange={v => set("live", v)} />
                <TweakToggle label="Show CPU/RAM rows" value={t.showCpu !== false}
                  onChange={v => set("showCpu", v)} />
              </TweakSection>
            </>
          )}
        </TweaksPanel>
      )}
    </div>
  );
}

function focusBtn(active){
  return {
    background: active ? "var(--sig-cyan)" : "transparent",
    color: active ? "var(--bg-0)" : "var(--fg-2)",
    border: `1px solid ${active ? "var(--sig-cyan)" : "var(--line)"}`,
    padding: "1px 8px", fontFamily: "var(--font-mono)", fontSize: 10,
    fontWeight: active ? 700 : 500, letterSpacing: "0.1em", cursor: "pointer",
  };
}

function TopBar({ now, live, qps, fps, stats }){
  return (
    <header style={{
      height: 50, background: "var(--bg-1)", borderBottom: "1px solid var(--line)",
      display: "flex", alignItems: "stretch",
    }}>
      <div style={{
        padding: "0 18px", display: "flex", alignItems: "center", gap: 12,
        borderRight: "1px solid var(--line)",
      }}>
        <div style={{ width: 22, height: 22, position: "relative" }}>
          <div style={{ position: "absolute", inset: 0, border: "1px solid var(--sig-cyan)" }} />
          <div style={{ position: "absolute", inset: 4, background: "var(--sig-cyan)", opacity: 0.3 }} />
          <div style={{ position: "absolute", inset: 7, background: "var(--sig-cyan)" }} />
        </div>
        <div>
          <div className="mono" style={{ fontSize: 12, fontWeight: 700, color: "var(--fg)", letterSpacing: "0.04em" }}>
            EDGE.PROFILER<span style={{ color: "var(--sig-cyan)" }}>/</span>RK3588
          </div>
          <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", marginTop: 1, letterSpacing: "0.1em" }}>
            v1.0.0 · build 2026.05.02 · 6 TOPS
          </div>
        </div>
      </div>

      <nav style={{ display: "flex", alignItems: "stretch" }}>
        {["DASHBOARD","PROFILE","AB EVAL","MODELS","LOGS"].map((t, i) => (
          <a key={t} href="#" style={{
            padding: "0 18px", display: "flex", alignItems: "center",
            borderRight: "1px solid var(--line)",
            color: i === 0 ? "var(--fg)" : "var(--fg-2)",
            fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: i === 0 ? 700 : 500,
            letterSpacing: "0.12em", textDecoration: "none",
            background: i === 0 ? "var(--bg-2)" : "transparent",
            borderBottom: i === 0 ? "2px solid var(--sig-cyan)" : "2px solid transparent",
          }}>{t}</a>
        ))}
      </nav>

      <div style={{ flex: 1 }} />

      <div style={{ display: "flex", alignItems: "center", gap: 18, padding: "0 18px" }}>
        <NavMetric label="QPS"  value={qps} color="var(--sig-cyan)" />
        <NavMetric label="FPS"  value={fps.toFixed(2)} color="var(--sig-amber)" />
        <NavMetric label="HIGH" value={stats.today_high} color="var(--sig-red)" />
        <span style={{ width: 1, height: 24, background: "var(--line)" }} />
        <span className="mono" style={{ fontSize: 11, color: "var(--fg-1)", fontVariantNumeric: "tabular-nums" }}>
          {fmtTime(now)}<span style={{ color: "var(--fg-3)" }}> UTC+8</span>
        </span>
        <StatusDot state={live ? "online" : "stale"} />
      </div>
    </header>
  );
}

function NavMetric({ label, value, color }){
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 5 }}>
      <span className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.14em" }}>{label}</span>
      <span className="mono" style={{ fontSize: 14, color, fontVariantNumeric: "tabular-nums", fontWeight: 600 }}>{value}</span>
    </div>
  );
}

function KPIStrip({ stats, avgTotal, fps, tick }){
  const A = stats.ab_compare.A, B = stats.ab_compare.B;
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "repeat(6, 1fr)",
      background: "var(--line)", gap: 1,
    }}>
      <MetricCell label="DEFECTS · 24h" value={fmtNumber(stats.total)} sub={`high · ${stats.today_high}`} flashKey={tick} tone="cyan" />
      <MetricCell label="AVG PIPELINE" value={Math.round(avgTotal)} unit="ms" sub={`fps · ${fps.toFixed(2)}`} tone="amber" />
      <MetricCell label="NPU CORE 2 · LOAD" value="78" unit="%" sub="Qwen3-VL pinned" tone="red" />
      <MetricCell label="JSON OK · B" value={`${(B.json_ok_rate * 100).toFixed(1)}`} unit="%" sub={`A · ${(A.json_ok_rate * 100).toFixed(1)}%`} tone="teal" />
      <MetricCell label="TTFT · B" value={Math.round(B.avg_ttft_ms)} unit="ms" sub={`-${Math.round((1 - B.avg_ttft_ms / A.avg_ttft_ms) * 100)}% vs A`} tone="green" />
      <MetricCell label="RSS · STEADY" value={Math.round(B.avg_rss_mb)} unit="MB" sub="of 16384 LPDDR4" tone="default" />
    </div>
  );
}

function BottomStatus({ now, stats, qps, live, tick }){
  return (
    <footer style={{
      height: 28, background: "var(--bg-1)", borderTop: "1px solid var(--line)",
      display: "flex", alignItems: "center",
      fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--fg-3)",
      letterSpacing: "0.06em",
    }}>
      <span style={{ padding: "0 14px", borderRight: "1px solid var(--line)", color: live ? "var(--sig-green)" : "var(--sig-amber)" }}>
        ● WS /ws/dashboard
      </span>
      <span style={{ padding: "0 14px", borderRight: "1px solid var(--line)" }}>edge_ts → server_ts · drift &lt; 220ms</span>
      <span style={{ padding: "0 14px", borderRight: "1px solid var(--line)" }}>events <span style={{ color: "var(--fg-1)" }}>{tick}</span></span>
      <span style={{ padding: "0 14px", borderRight: "1px solid var(--line)" }}>qps <span style={{ color: "var(--sig-cyan)" }}>{qps}</span></span>
      <span style={{ padding: "0 14px", borderRight: "1px solid var(--line)" }}>db · vision.db (WAL)</span>
      <span style={{ flex: 1 }} />
      <span style={{ padding: "0 14px", borderLeft: "1px solid var(--line)" }}>schema_version v1</span>
      <span style={{ padding: "0 14px", borderLeft: "1px solid var(--line)" }}>{fmtDateTime(now)}</span>
    </footer>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
