// V3 App — chip-centric dashboard with Overview + Profile pages.

const { useState: _appS3, useEffect: _appE3, useMemo: _appM3 } = React;

const STAGE_DURATIONS_MS_TOTAL = 300 + 280 + 480 + 1700 + 320 + 380;

// Accent color presets — curated palette
const ACCENT_PRESETS = {
  lime:    { acc: "#c1ff72", glow: "rgba(193,255,114,0.22)" },
  amber:   { acc: "#ffbf5c", glow: "rgba(255,191,92,0.22)" },
  cyan:    { acc: "#5ad6ff", glow: "rgba(90,214,255,0.22)" },
  magenta: { acc: "#ff6ec7", glow: "rgba(255,110,199,0.22)" },
};

function App(){
  const tweaksHook = window.useTweaks || (() => [{}, () => {}]);
  const [tweaks, setTweak] = tweaksHook(window.__TWEAK_DEFAULTS__V3 || {});
  const accentKey = tweaks.accentHue || "lime";
  const accentPreset = ACCENT_PRESETS[accentKey] || ACCENT_PRESETS.lime;
  const speed = tweaks.animSpeed ?? 1;
  const live = tweaks.live !== false;
  const showTraces = tweaks.showTraces !== false;

  // sync accent CSS variables on document root
  _appE3(() => {
    document.documentElement.style.setProperty("--acc", accentPreset.acc);
    document.documentElement.style.setProperty("--acc-glow", accentPreset.glow);
  }, [accentKey, accentPreset.acc, accentPreset.glow]);

  // routing — hash based, so refresh keeps page
  const [route, setRoute] = _appS3(() => (typeof window !== "undefined" ? (window.location.hash.replace("#", "") || "overview") : "overview"));
  _appE3(() => {
    const onHash = () => setRoute(window.location.hash.replace("#", "") || "overview");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const navigate = key => {
    window.location.hash = "#" + key;
  };

  const [defects, setDefects] = _appS3(() => seedDefects(60));
  const [now, setNow] = _appS3(new Date());

  // NPU loads — for chip diagram
  const [npuLoads, setNpuLoads] = _appS3([22, 41, 78]);
  _appE3(() => {
    const id = setInterval(() => {
      setNpuLoads([
        Math.max(8,  Math.min(35, 22 + (Math.random() - 0.5) * 14)),
        Math.max(20, Math.min(70, 41 + (Math.random() - 0.5) * 18)),
        Math.max(60, Math.min(95, 78 + (Math.random() - 0.5) * 12)),
      ]);
    }, 1200 / Math.max(speed, 0.25));
    return () => clearInterval(id);
  }, [speed]);

  _appE3(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const phase = useFrameSimulator({
    live, speed,
    onComplete: () => {
      const d = makeDefect({ ts: new Date() });
      d._new = true;
      setDefects(prev => [d, ...prev].slice(0, 80));
    },
  });
  const cpuLoads = useCpuLoads({ phase, speed });

  const stats = _appM3(() => buildStats(defects), [defects]);
  const lastDefect = defects[0] || null;
  const totalFrames = defects.length;
  const fps = (60 / ((STAGE_DURATIONS_MS_TOTAL / speed) / 1000)).toFixed(2);

  return (
    <div style={{ minHeight: "100vh" }}>
      <TopBar now={now} stats={stats} live={live} route={route} navigate={navigate} />

      {route === "overview" && (
        <OverviewPage
          stats={stats} fps={fps} totalFrames={totalFrames}
          phase={phase} npuLoads={npuLoads} cpuLoads={cpuLoads}
          showTraces={showTraces} accent={accentPreset.acc}
          lastDefect={lastDefect} defects={defects}
        />
      )}

      {route === "profile" && (
        <ProfileShell defects={defects} accent={accentPreset.acc} />
      )}

      {route === "ab" && (
        <ABShell stats={stats} />
      )}

      <BottomBar now={now} stats={stats} live={live} route={route} />

      {window.TweaksPanel && (
        <TweaksPanel title="Tweaks">
          <TweakSection label="Theme">
            <TweakColor label="Accent color"
                        value={accentKey}
                        onChange={v => setTweak("accentHue", v)}
                        options={[
                          { value: "lime",    swatch: "#c1ff72" },
                          { value: "amber",   swatch: "#ffbf5c" },
                          { value: "cyan",    swatch: "#5ad6ff" },
                          { value: "magenta", swatch: "#ff6ec7" },
                        ]} />
          </TweakSection>
          <TweakSection label="Simulation">
            <TweakToggle label="Live frame stream"  value={live}
                         onChange={v => setTweak("live", v)} />
            <TweakSlider label="Animation speed"
                         value={speed}
                         min={0.25} max={3} step={0.25}
                         onChange={v => setTweak("animSpeed", v)} />
            <TweakToggle label="NPU trace packets"   value={showTraces}
                         onChange={v => setTweak("showTraces", v)} />
          </TweakSection>
          <TweakSection label="Navigate">
            <TweakRadio label="Page" value={route}
                        onChange={v => navigate(v)}
                        options={[
                          { value: "overview", label: "Overview" },
                          { value: "profile",  label: "Profile" },
                        ]} />
          </TweakSection>
        </TweaksPanel>
      )}
    </div>
  );
}

// ── Custom color tweak (swatch picker, since starter doesn't expose object-mode TweakColor) ──
function TweakColor({ label, value, options, onChange }){
  return (
    <div style={{ padding: "8px 12px" }}>
      <div className="eyebrow" style={{ fontSize: 9, marginBottom: 6 }}>{label}</div>
      <div style={{ display: "flex", gap: 6 }}>
        {options.map(o => (
          <button key={o.value} onClick={() => onChange(o.value)}
            title={o.value}
            style={{
              width: 32, height: 32,
              background: o.swatch,
              border: `2px solid ${value === o.value ? "var(--fg)" : "var(--line)"}`,
              cursor: "pointer", padding: 0,
              boxShadow: value === o.value ? `0 0 8px ${o.swatch}` : "none",
            }} />
        ))}
      </div>
    </div>
  );
}

// ── Page shells ──────────────────────────────────────────────────────────
function OverviewPage({ stats, fps, totalFrames, phase, npuLoads, cpuLoads, showTraces, accent, lastDefect, defects }){
  return (
    <main style={{ maxWidth: 1480, margin: "0 auto", padding: "24px 32px 80px", display: "flex", flexDirection: "column", gap: 28 }}>
      <section style={{ paddingTop: 8 }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "4px 12px", border: "1px solid var(--line)", borderRadius: 100, marginBottom: 18 }}>
          <span style={{ width: 6, height: 6, background: accent, borderRadius: "50%", boxShadow: `0 0 6px ${accent}` }} />
          <span className="mono" style={{ fontSize: 10, color: "var(--fg-2)", letterSpacing: "0.1em" }}>EDGE NODE · TRACK A · RK3588 16GB</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.4fr) minmax(0, 1fr)", gap: 60, alignItems: "flex-end" }}>
          <div>
            <h1 style={{
              margin: 0, fontSize: 52, fontWeight: 600, lineHeight: 1.04,
              letterSpacing: "-0.03em", color: "var(--fg)",
            }}>
              Three-stage vision pipeline,
              <span style={{ display: "block", color: "var(--fg-3)" }}>
                running on a <span style={{ color: accent }}>$80 SBC</span>.
              </span>
            </h1>
            <p style={{ color: "var(--fg-2)", fontSize: 15, lineHeight: 1.65, marginTop: 20, maxWidth: 620 }}>
              EfficientAD-S finds anomalies. FastSAM segments them. Qwen3-VL-2B describes them — all on one Rockchip RK3588 NPU, INT8 / W8A8 quantized, async-pipelined across three cores plus an 8-core ARM cluster.
            </p>
          </div>
          <KPIStack stats={stats} fps={fps} totalFrames={totalFrames} accent={accent} />
        </div>
      </section>

      <section>
        <RK3588Twin phase={phase} npuLoads={npuLoads} cpuLoads={cpuLoads}
                    ramUsed={9.2 + (npuLoads[2]/100) * 1.2}
                    showTraces={showTraces} accent={accent} />
      </section>

      <section style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <SectionHeader number="02" title="Latest emitted frame"
                       caption="What the backend just received via POST /api/edge/report" />
        <FrameInspector defect={lastDefect} />
      </section>

      <section style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <SectionHeader number="03" title="Inference strategy A/B"
                       caption="Two variants run on the same hardware — pick the one that ships" />
        <ABCompareV3 stats={stats} />
      </section>

      <section style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <SectionHeader number="04" title="Detection feed"
                       caption="Live WebSocket stream from /ws/dashboard · click to inspect" />
        <RecentStream defects={defects} />
      </section>
    </main>
  );
}

function ProfileShell({ defects, accent }){
  return (
    <main style={{ maxWidth: 1480, margin: "0 auto", padding: "24px 32px 80px", display: "flex", flexDirection: "column", gap: 28 }}>
      <section style={{ paddingTop: 8 }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "4px 12px", border: "1px solid var(--line)", borderRadius: 100, marginBottom: 18 }}>
          <span style={{ width: 6, height: 6, background: accent, borderRadius: "50%", boxShadow: `0 0 6px ${accent}` }} />
          <span className="mono" style={{ fontSize: 10, color: "var(--fg-2)", letterSpacing: "0.1em" }}>PROFILER · CHROME TRACE</span>
        </div>
        <h1 style={{
          margin: 0, fontSize: 44, fontWeight: 600, lineHeight: 1.05,
          letterSpacing: "-0.025em", color: "var(--fg)",
        }}>
          Per-frame timeline,
          <span style={{ display: "block", color: "var(--fg-3)" }}>
            across <span style={{ color: accent }}>4 threads · 3 NPU cores · 8 ARM cores</span>.
          </span>
        </h1>
        <p style={{ color: "var(--fg-2)", fontSize: 15, lineHeight: 1.65, marginTop: 20, maxWidth: 720 }}>
          Each defect record ships with a Chrome-trace-format event log. Drop it into <span className="mono">chrome://tracing</span> or <span className="mono">perfetto.dev</span>, or just inspect it here. The critical path is dominated by NPU.2 (Qwen3-VL) — every ms shaved off prompt or decode flows straight to E2E FPS.
        </p>
      </section>

      <ProfilePage defects={defects} accent={accent} />
    </main>
  );
}

function ABShell({ stats }){
  return (
    <main style={{ maxWidth: 1480, margin: "0 auto", padding: "24px 32px 80px", display: "flex", flexDirection: "column", gap: 28 }}>
      <ABCompareV3 stats={stats} />
    </main>
  );
}

// ── Bars ─────────────────────────────────────────────────────────────────
function TopBar({ now, live, route, navigate }){
  const navItems = [
    { key: "overview", label: "Overview" },
    { key: "profile",  label: "Profile" },
    { key: "ab",       label: "AB Eval" },
    { key: "models",   label: "Models", disabled: true },
    { key: "logs",     label: "Logs",   disabled: true },
  ];
  return (
    <header style={{
      padding: "18px 32px", maxWidth: 1480, margin: "0 auto",
      display: "flex", justifyContent: "space-between", alignItems: "center",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ width: 30, height: 30, position: "relative" }}>
          <div style={{ position: "absolute", inset: 0, border: "1px solid var(--acc)", transform: "rotate(45deg)" }} />
          <div style={{ position: "absolute", inset: 6, background: "var(--acc)", opacity: 0.4, transform: "rotate(45deg)" }} />
          <div style={{ position: "absolute", inset: 11, background: "var(--acc)", transform: "rotate(45deg)" }} />
        </div>
        <div>
          <div style={{ fontFamily: "var(--font-sans)", fontSize: 15, fontWeight: 700, letterSpacing: "-0.01em" }}>
            Edge Vision <span style={{ color: "var(--fg-3)", fontWeight: 400 }}>· RK3588 twin</span>
          </div>
          <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginTop: 1 }}>
            v1.0.0 · mvtec-ad · qwen3-vl-2b-w8a8
          </div>
        </div>
      </div>

      <nav style={{ display: "flex", gap: 24 }}>
        {navItems.map(item => {
          const active = route === item.key;
          return (
            <a key={item.key} href={item.disabled ? "#" : `#${item.key}`}
               onClick={e => { if (item.disabled) e.preventDefault(); }}
               style={{
                 color: active ? "var(--fg)" : (item.disabled ? "var(--fg-4)" : "var(--fg-2)"),
                 fontSize: 13, fontWeight: 500,
                 textDecoration: "none",
                 paddingBottom: 2, borderBottom: active ? "1px solid var(--acc)" : "1px solid transparent",
                 cursor: item.disabled ? "not-allowed" : "pointer",
               }}>{item.label}</a>
          );
        })}
      </nav>

      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{
            width: 7, height: 7, background: live ? "var(--ok)" : "var(--warn)",
            borderRadius: "50%", boxShadow: `0 0 6px ${live ? "var(--ok)" : "var(--warn)"}`,
            animation: live ? "pulse-dot 1.4s infinite" : "none",
          }} />
          <span className="mono" style={{ fontSize: 11, color: live ? "var(--ok)" : "var(--warn)" }}>
            {live ? "LIVE" : "PAUSED"}
          </span>
        </span>
        <span className="mono" style={{ fontSize: 11, color: "var(--fg-2)" }}>{fmtTime(now)}</span>
      </div>
    </header>
  );
}

function KPIStack({ stats, fps, totalFrames, accent }){
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, auto)", gap: 28, alignItems: "flex-end" }}>
      <KPI big label="Frames today" value={fmtNumber(totalFrames * 38 + 4200)} />
      <KPI big label="Defects" value={fmtNumber(stats.total)} sub={`${stats.today_high} high-severity`} />
      <KPI big label="E2E FPS" value={fps} color={accent} sub="end-to-end pipeline" />
    </div>
  );
}

function KPI({ label, value, unit, sub, color = "var(--fg)", big }){
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <span className="eyebrow">{label}</span>
      <span style={{ display: "flex", alignItems: "baseline", gap: 4, marginTop: 4 }}>
        <span className="mono" style={{
          fontSize: big ? 30 : 18, fontWeight: 500, color,
          letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums",
        }}>{value}</span>
        {unit && <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>{unit}</span>}
      </span>
      {sub && <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>{sub}</span>}
    </div>
  );
}

function SectionHeader({ number, title, caption }){
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 18 }}>
      <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)", fontWeight: 500 }}>{number}</span>
      <div style={{ flex: 1 }}>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em" }}>{title}</h2>
        {caption && <p style={{ margin: "4px 0 0", color: "var(--fg-2)", fontSize: 13 }}>{caption}</p>}
      </div>
    </div>
  );
}

function BottomBar({ now, stats, live, route }){
  return (
    <footer style={{
      borderTop: "1px solid var(--line-soft)", marginTop: 40,
      maxWidth: 1480, margin: "40px auto 0", padding: "20px 32px",
      display: "flex", justifyContent: "space-between", alignItems: "center",
      color: "var(--fg-3)", fontFamily: "var(--font-mono)", fontSize: 10,
    }}>
      <div style={{ display: "flex", gap: 18 }}>
        <span>● WS /ws/dashboard {live ? "open" : "paused"}</span>
        <span>schema v1</span>
        <span>vision.db · WAL</span>
        <span>route · #{route}</span>
        <span>events n={stats.total}</span>
      </div>
      <div>build 2026.05.14 · UTC+8 · {fmtDateTime(now)}</div>
    </footer>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
