// V4 App shell — top nav (5 enabled routes), Overview hero with KPI tiles, drawer wiring.

const { useState: _appS, useEffect: _appE, useMemo: _appM } = React;

const ACCENT_PRESETS = {
  lime:    { acc: "#c1ff72", glow: "rgba(193,255,114,0.22)" },
  nvidia:  { acc: "#76b900", glow: "rgba(118,185,0,0.22)"   },
  cyan:    { acc: "#5ad6ff", glow: "rgba(90,214,255,0.22)"  },
  amber:   { acc: "#ffbf5c", glow: "rgba(255,191,92,0.22)"  },
};

const STAGE_DURATIONS_MS_TOTAL = 320 + 280 + 480 + 1700 + 320 + 380;

function App(){
  const tweaksHook = window.useTweaks || (() => [{}, () => {}]);
  const [tweaks, setTweak] = tweaksHook(window.__TWEAK_DEFAULTS__V4 || {});
  const accentKey = tweaks.accentHue || "lime";
  const accentPreset = ACCENT_PRESETS[accentKey] || ACCENT_PRESETS.lime;
  const speed = tweaks.animSpeed ?? 1;
  const live = tweaks.live !== false;
  const showTraces = tweaks.showTraces !== false;
  const twinMode = tweaks.twinMode || "product";

  _appE(() => {
    document.documentElement.style.setProperty("--acc", accentPreset.acc);
    document.documentElement.style.setProperty("--acc-glow", accentPreset.glow);
  }, [accentKey, accentPreset.acc, accentPreset.glow]);

  // routing
  const [route, setRoute] = _appS(() =>
    (typeof window !== "undefined" ? (window.location.hash.replace("#", "") || "overview") : "overview"));
  _appE(() => {
    const onHash = () => setRoute(window.location.hash.replace("#", "") || "overview");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const navigate = key => { window.location.hash = "#" + key; };

  const [defects, setDefects] = _appS(() => seedDefects(80));
  const [now, setNow] = _appS(new Date());
  const [selectedDefect, setSelectedDefect] = _appS(null);
  const [profileSeedIdx, setProfileSeedIdx] = _appS(0);

  // Edge config (drives Models page + AB matrix)
  const [activeConfig, setActiveConfig] = _appS({ model_size: "2B", variant: "lora" });

  // NPU loads
  const [npuLoads, setNpuLoads] = _appS([22, 41, 78]);
  _appE(() => {
    const id = setInterval(() => {
      setNpuLoads([
        Math.max(8,  Math.min(35, 22 + (Math.random() - 0.5) * 14)),
        Math.max(20, Math.min(70, 41 + (Math.random() - 0.5) * 18)),
        Math.max(60, Math.min(95, 78 + (Math.random() - 0.5) * 12)),
      ]);
    }, 1200 / Math.max(speed, 0.25));
    return () => clearInterval(id);
  }, [speed]);

  _appE(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const phase = useFrameSimulator({
    live, speed,
    onComplete: () => {
      const d = makeDefect({ ts: new Date() });
      d._new = true;
      setDefects(prev => [d, ...prev].slice(0, 100));
    },
  });
  const cpuLoads = useCpuLoads({ phase, speed });

  const stats = _appM(() => buildStats(defects), [defects]);
  const lastDefect = defects[0] || null;
  const fps = (60 / ((STAGE_DURATIONS_MS_TOTAL / speed) / 1000)).toFixed(2);
  const ramUsed = (activeConfig.model_size === "4B" ? 11.4 : 5.0) + (npuLoads[2]/100) * 0.6;

  const openProfileForDefect = d => {
    const idx = defects.findIndex(x => x.id === d.id);
    setProfileSeedIdx(idx >= 0 ? idx : 0);
    setSelectedDefect(null);
    navigate("profile");
  };

  return (
    <div style={{ minHeight: "100vh" }}>
      <TopBar now={now} stats={stats} live={live} route={route} navigate={navigate} accent={accentPreset.acc} />

      <main style={{ maxWidth: 1480, margin: "0 auto", padding: "20px 32px 80px",
                     display: "flex", flexDirection: "column", gap: 28 }}>
        {route === "overview" && (
          <OverviewPage
            stats={stats} fps={fps} totalFrames={defects.length}
            phase={phase} npuLoads={npuLoads} cpuLoads={cpuLoads}
            showTraces={showTraces} accent={accentPreset.acc}
            lastDefect={lastDefect} defects={defects}
            twinMode={twinMode} setTwinMode={v => setTweak("twinMode", v)}
            selectedDefect={selectedDefect} setSelectedDefect={setSelectedDefect}
            onOpenProfile={openProfileForDefect}
            activeConfig={activeConfig}
            ramUsed={ramUsed} />
        )}

        {route === "profile" && (
          <ProfileShell defects={defects} accent={accentPreset.acc} initialFrameIdx={profileSeedIdx} />
        )}

        {route === "ab" && (
          <ABShell stats={stats} activeConfig={activeConfig} accent={accentPreset.acc} />
        )}

        {route === "models" && (
          <ModelsPage stats={stats}
                      activeConfig={activeConfig}
                      onChangeConfig={setActiveConfig}
                      accent={accentPreset.acc} />
        )}

        {route === "logs" && (
          <LogsPage accent={accentPreset.acc} />
        )}
      </main>

      <BottomBar now={now} stats={stats} live={live} route={route} activeConfig={activeConfig} />

      {/* Detail drawer */}
      <DetailDrawer defect={selectedDefect}
                    onClose={() => setSelectedDefect(null)}
                    onOpenProfile={openProfileForDefect} />

      {window.TweaksPanel && (
        <TweaksPanel title="Tweaks">
          <TweakSection label="Theme">
            <TweakColor label="Accent" value={accentKey}
                        onChange={v => setTweak("accentHue", v)}
                        options={[
                          { value: "lime",    swatch: "#c1ff72" },
                          { value: "nvidia",  swatch: "#76b900" },
                          { value: "cyan",    swatch: "#5ad6ff" },
                          { value: "amber",   swatch: "#ffbf5c" },
                        ]} />
          </TweakSection>
          <TweakSection label="芯片孪生">
            <TweakRadio label="Mode" value={twinMode}
                        onChange={v => setTweak("twinMode", v)}
                        options={[
                          { value: "product", label: "Product" },
                          { value: "xray",    label: "X-Ray" },
                          { value: "trace",   label: "Trace" },
                        ]} />
            <TweakToggle label="显示数据包追踪" value={showTraces}
                         onChange={v => setTweak("showTraces", v)} />
          </TweakSection>
          <TweakSection label="模拟参数">
            <TweakToggle label="实时帧流" value={live}
                         onChange={v => setTweak("live", v)} />
            <TweakSlider label="动画速度" value={speed}
                         min={0.25} max={3} step={0.25}
                         onChange={v => setTweak("animSpeed", v)} />
          </TweakSection>
          <TweakSection label="页面导航">
            <TweakSelect label="Page" value={route}
                         onChange={v => navigate(v)}
                         options={[
                           { value: "overview", label: "总览" },
                           { value: "profile",  label: "性能剖析" },
                           { value: "ab",       label: "变体对比" },
                           { value: "models",   label: "模型" },
                           { value: "logs",     label: "日志" },
                         ]} />
          </TweakSection>
        </TweaksPanel>
      )}
    </div>
  );
}

// ── Color tweak (curated swatches) ───────────────────────────────────────
function TweakColor({ label, value, options, onChange }){
  return (
    <div style={{ padding: "8px 12px" }}>
      <div className="eyebrow" style={{ fontSize: 9, marginBottom: 6 }}>{label}</div>
      <div style={{ display: "flex", gap: 6 }}>
        {options.map(o => (
          <button key={o.value} onClick={() => onChange(o.value)} title={o.value}
            style={{
              width: 30, height: 30, background: o.swatch,
              border: `2px solid ${value === o.value ? "var(--fg)" : "var(--line)"}`,
              cursor: "pointer", padding: 0,
              boxShadow: value === o.value ? `0 0 8px ${o.swatch}` : "none",
            }} />
        ))}
      </div>
    </div>
  );
}

// ── Overview page ────────────────────────────────────────────────────────
function OverviewPage({ stats, fps, totalFrames, phase, npuLoads, cpuLoads, showTraces, accent,
                        lastDefect, defects, twinMode, setTwinMode,
                        selectedDefect, setSelectedDefect, onOpenProfile,
                        activeConfig, ramUsed }){
  return (
    <>
      {/* Hero block — 4 KPI tiles only */}
      <section data-screen-label="Overview Hero">
        <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "4px 12px",
                      border: "1px solid var(--line)", borderRadius: 100, marginBottom: 18 }}>
          <span style={{ width: 6, height: 6, background: accent, borderRadius: "50%", boxShadow: `0 0 6px ${accent}` }} />
          <span className="mono" style={{ fontSize: 10, color: "var(--fg-2)", letterSpacing: "0.1em" }}>
            边缘节点 001 · RK3588 16GB · FastAPI + WS · Schema v1.1
          </span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.3fr) minmax(0, 1fr)", gap: 60, alignItems: "flex-end" }}>
          <div>
            <h1 style={{
              margin: 0, fontSize: 52, fontWeight: 600, lineHeight: 1.04,
              letterSpacing: "-0.03em", color: "var(--fg)",
            }}>
              三阶段视觉流水线，
              <span style={{ display: "block", color: "var(--fg-3)" }}>
                量化部署在一块 <span style={{ color: accent }}>$80 单板机</span>上。
              </span>
            </h1>
            <p style={{ color: "var(--fg-2)", fontSize: 15, lineHeight: 1.65, marginTop: 20, maxWidth: 620 }}>
              EfficientAD-S 检测异常，FastSAM-s 精确定位，Qwen3-VL 输出描述——全部运行在同一块 Rockchip RK3588 NPU 上，
              INT8 / W8A8 量化，跨三核异步流水线。前端仅消费 FastAPI REST + WebSocket，不直连 RK3588。
            </p>
            <div style={{ display: "flex", gap: 8, marginTop: 20, flexWrap: "wrap" }}>
              <ProofChip text="INT8 / W8A8 量化" />
              <ProofChip text="4 线程 C++ 流水线" />
              <ProofChip text="REST + WebSocket" />
            </div>
          </div>
          <KPI4 stats={stats} fps={fps} ramUsed={ramUsed} accent={accent} />
        </div>
      </section>

      {/* Digital twin */}
      <section data-screen-label="Digital Twin">
        <RK3588Twin phase={phase} npuLoads={npuLoads} cpuLoads={cpuLoads}
                    ramUsed={ramUsed}
                    mode={twinMode} onModeChange={setTwinMode}
                    showTraces={showTraces} accent={accent} />
      </section>

      {/* Latest frame inspector */}
      <section style={{ display: "flex", flexDirection: "column", gap: 14 }} data-screen-label="Frame Inspector">
        <SectionHeader number="02" title="最新帧"
                       caption="后端通过 POST /api/edge/report 收到的最新帧 · JSON / 指标 / 溯源" />
        <FrameInspector defect={lastDefect} />
      </section>

      {/* Detection feed */}
      <section style={{ display: "flex", flexDirection: "column", gap: 14 }} data-screen-label="Detection Feed">
        <SectionHeader number="03" title="检测流"
                       caption="来自 /ws/dashboard 的实时 WebSocket 流 · 点击卡片查看详情" />
        <RecentStream defects={defects}
                      onSelect={setSelectedDefect}
                      selectedId={selectedDefect?.id} />
      </section>
    </>
  );
}

function ProofChip({ text }){
  return (
    <span className="mono" style={{
      fontSize: 11, padding: "5px 11px",
      border: "1px solid var(--line)",
      background: "var(--bg-1)",
      color: "var(--fg-2)", letterSpacing: "0.04em",
      display: "inline-flex", alignItems: "center", gap: 6,
    }}>
      <span style={{ width: 4, height: 4, background: "var(--acc)" }} />
      {text}
    </span>
  );
}

// 4 KPI tiles only (per spec)
function KPI4({ stats, fps, ramUsed, accent }){
  const e2eMs = (1 / parseFloat(fps) * 1000).toFixed(0);
  const ttftAvg = Math.round(
    (stats.ab_compare["2B_lora"]?.avg_ttft_ms || 1100));
  const jsonRate = Math.round(
    Object.values(stats.ab_compare).reduce((s, v) => s + (v.json_ok_rate || 0) * (v.count || 0), 0) /
    Math.max(1, Object.values(stats.ab_compare).reduce((s, v) => s + (v.count || 0), 0)) * 100);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1,
                  background: "var(--line)", border: "1px solid var(--line)" }}>
      <KPITile label="端到端延迟"  value={e2eMs}  unit="ms"   sub="异常检测 → JSON" color={accent} />
      <KPITile label="VLM 首字延迟" value={ttftAvg} unit="ms"  sub="Qwen3-VL · p50" />
      <KPITile label="JSON 解析率"  value={jsonRate} unit="%"  sub={`共 ${stats.total} 帧`} color="var(--ok)" />
      <KPITile label="LPDDR4 占用"  value={ramUsed.toFixed(1)} unit="/ 16 GB" sub="VLM + 缓冲" />
    </div>
  );
}
function KPITile({ label, value, unit, sub, color = "var(--fg)" }){
  return (
    <div style={{ background: "var(--bg-1)", padding: "14px 18px" }}>
      <div className="eyebrow">{label}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 5, marginTop: 6 }}>
        <span className="mono" style={{
          fontSize: 30, fontWeight: 500, color,
          letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums",
        }}>{value}</span>
        <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>{unit}</span>
      </div>
      <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginTop: 4 }}>{sub}</div>
    </div>
  );
}

// ── Route shells ─────────────────────────────────────────────────────────
function ProfileShell({ defects, accent, initialFrameIdx }){
  return (
    <>
      <section style={{ paddingTop: 0 }} data-screen-label="Profile Hero">
        <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "4px 12px",
                      border: "1px solid var(--line)", borderRadius: 100, marginBottom: 18 }}>
          <span style={{ width: 6, height: 6, background: accent, borderRadius: "50%", boxShadow: `0 0 6px ${accent}` }} />
          <span className="mono" style={{ fontSize: 10, color: "var(--fg-2)", letterSpacing: "0.1em" }}>性能剖析 · 瓶颈分析</span>
        </div>
        <h1 style={{ margin: 0, fontSize: 44, fontWeight: 600, lineHeight: 1.05, letterSpacing: "-0.025em" }}>
          逐帧时序分析，
          <span style={{ display: "block", color: "var(--fg-3)" }}>
            横跨 <span style={{ color: accent }}>4 线程 · 3 NPU 核 · 8 ARM 核</span>。
          </span>
        </h1>
        <p style={{ color: "var(--fg-2)", fontSize: 15, lineHeight: 1.65, marginTop: 16, maxWidth: 720 }}>
          每条缺陷记录附带 Chrome-trace 格式事件日志。关键路径由 NPU.2（Qwen3-VL）主导——提示词或解码每节省 1ms，端到端帧率直接提升。
        </p>
      </section>
      <ProfilePage defects={defects} accent={accent} initialFrameIdx={initialFrameIdx} />
    </>
  );
}

function ABShell({ stats, activeConfig, accent }){
  return (
    <>
      <section style={{ paddingTop: 0 }} data-screen-label="AB Hero">
        <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "4px 12px",
                      border: "1px solid var(--line)", borderRadius: 100, marginBottom: 18 }}>
          <span style={{ width: 6, height: 6, background: accent, borderRadius: "50%", boxShadow: `0 0 6px ${accent}` }} />
          <span className="mono" style={{ fontSize: 10, color: "var(--fg-2)", letterSpacing: "0.1em" }}>变体对比 · 矩阵分析</span>
        </div>
        <h1 style={{ margin: 0, fontSize: 44, fontWeight: 600, lineHeight: 1.05, letterSpacing: "-0.025em" }}>
          四个变体，
          <span style={{ display: "block", color: "var(--fg-3)" }}>
            一个<span style={{ color: accent }}>已部署</span>方案。
          </span>
        </h1>
      </section>
      <ABMatrix stats={stats} activeConfig={activeConfig} />
    </>
  );
}

// ── Top / bottom bars ────────────────────────────────────────────────────
function TopBar({ now, live, route, navigate, accent }){
  const navItems = [
    { key: "overview", label: "总览" },
    { key: "profile",  label: "性能剖析" },
    { key: "ab",       label: "变体对比" },
    { key: "models",   label: "模型" },
    { key: "logs",     label: "日志" },
  ];
  return (
    <header style={{
      padding: "18px 32px", maxWidth: 1480, margin: "0 auto",
      display: "flex", justifyContent: "space-between", alignItems: "center", gap: 24,
    }}>
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
        {navItems.map(item => {
          const active = route === item.key;
          return (
            <a key={item.key} href={`#${item.key}`}
               style={{
                 color: active ? "var(--fg)" : "var(--fg-2)",
                 fontSize: 13, fontWeight: 500, textDecoration: "none",
                 paddingBottom: 2, borderBottom: active ? `1px solid ${accent}` : "1px solid transparent",
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
            {live ? "实时" : "已暂停"}
          </span>
        </span>
        <span className="mono" style={{ fontSize: 11, color: "var(--fg-2)" }}>{fmtTime(now)}</span>
      </div>
    </header>
  );
}

function Logo({ accent }){
  return (
    <div style={{ width: 28, height: 28, position: "relative" }}>
      <div style={{ position: "absolute", inset: 0, border: `1px solid ${accent}`, transform: "rotate(45deg)" }} />
      <div style={{ position: "absolute", inset: 5, background: accent, opacity: 0.4, transform: "rotate(45deg)" }} />
      <div style={{ position: "absolute", inset: 10, background: accent, transform: "rotate(45deg)" }} />
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

function BottomBar({ now, stats, live, route, activeConfig }){
  return (
    <footer style={{
      borderTop: "1px solid var(--line-soft)",
      maxWidth: 1480, margin: "40px auto 0", padding: "20px 32px",
      display: "flex", justifyContent: "space-between", alignItems: "center",
      color: "var(--fg-3)", fontFamily: "var(--font-mono)", fontSize: 10,
      flexWrap: "wrap", gap: 12,
    }}>
      <div style={{ display: "flex", gap: 18, flexWrap: "wrap" }}>
        <span>● WS /ws/dashboard {live ? "已连接" : "已暂停"}</span>
        <span>schema v1.1</span>
        <span>vision.db · WAL</span>
        <span>路由 · #{route}</span>
        <span>事件数 n={stats.total}</span>
        <span>变体 · {activeConfig.model_size}_{activeConfig.variant}</span>
      </div>
      <div>build 2026.05.18 · UTC+8 · {fmtDateTime(now)}</div>
    </footer>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
