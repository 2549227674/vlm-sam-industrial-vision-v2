// RK3588 Digital Twin — v4
// 3 modes: Product (clean stage labels) · X-Ray (NPU+CPU+LPDDR+Mali) · Trace (animated packets + timing)
// NVIDIA-inspired: black surfaces, single accent, hairline borders, 2-4px radius, no soft shadows.

const { useState: _twS, useEffect: _twE, useMemo: _twM, useRef: _twR } = React;

const STAGE_DURATIONS_MS = { capture: 320, core0: 280, core1: 480, core2: 1700, upload: 320, idle: 380 };
const STAGE_REAL_MS      = { core0: 4.8, core1: 50, core2: 2300 };

function useFrameSimulator({ live, speed = 1, onComplete }){
  const [phase, setPhase] = _twS({ stage: "idle", frameId: null, startedAt: 0 });
  const tRef = _twR();
  const speedRef = _twR(speed); speedRef.current = speed;

  _twE(() => {
    if (!live) return;
    let cancelled = false;
    function tx(next, frameId, delay){
      tRef.current = setTimeout(() => {
        if (cancelled) return;
        setPhase({ stage: next, frameId, startedAt: performance.now() });
        const scale = speedRef.current > 0 ? 1 / speedRef.current : 1;
        if (next === "idle"){
          if (onComplete) onComplete(frameId);
          tx("capture", `F-${Date.now().toString().slice(-5)}`, STAGE_DURATIONS_MS.idle * scale);
        } else if (next === "capture") tx("core0", frameId, STAGE_DURATIONS_MS.capture * scale);
        else if (next === "core0")     tx("core1", frameId, STAGE_DURATIONS_MS.core0 * scale);
        else if (next === "core1")     tx("core2", frameId, STAGE_DURATIONS_MS.core1 * scale);
        else if (next === "core2")     tx("upload", frameId, STAGE_DURATIONS_MS.core2 * scale);
        else if (next === "upload")    tx("idle",   frameId, STAGE_DURATIONS_MS.upload * scale);
      }, delay);
    }
    tx("capture", `F-${Date.now().toString().slice(-5)}`, 200);
    return () => { cancelled = true; clearTimeout(tRef.current); };
  }, [live]);

  return phase;
}

function useCpuLoads({ phase, speed = 1 }){
  const [loads, setLoads] = _twS(() => [22, 14, 36, 18, 8, 6, 9, 5]);
  _twE(() => {
    const id = setInterval(() => {
      setLoads(prev => prev.map((v, i) => {
        let target;
        if      (phase.stage === "core0"  && i === 0) target = 65;
        else if (phase.stage === "core1"  && i === 1) target = 72;
        else if (phase.stage === "core2"  && i === 2) target = 88;
        else if (phase.stage === "upload" && i === 4) target = 42;
        else target = i < 4 ? 18 + Math.random() * 16 : 5 + Math.random() * 12;
        return Math.max(0, Math.min(100, v + (target - v) * 0.35 + (Math.random() - 0.5) * 6));
      }));
    }, 600 / Math.max(speed, 0.25));
    return () => clearInterval(id);
  }, [phase.stage, speed]);
  return loads;
}

// ── Top-level component ───────────────────────────────────────────────────
function RK3588Twin({ phase, npuLoads, cpuLoads, mode = "product", showTraces = true,
                     temp = 62.4, power = 4.8, ramUsed = 9.2, accent = "var(--acc)",
                     onModeChange }){
  return (
    <div style={{
      position: "relative", width: "100%",
      background: "var(--bg-1)",
      border: "1px solid var(--line)",
      overflow: "hidden",
    }}>
      <TwinHeader temp={temp} power={power} ramUsed={ramUsed} accent={accent}
                  mode={mode} onModeChange={onModeChange} />

      {/* SVG stage */}
      <ChipStage phase={phase} npuLoads={npuLoads} cpuLoads={cpuLoads}
                 mode={mode} showTraces={showTraces} accent={accent} ramUsed={ramUsed} />

      <FrameJourney phase={phase} accent={accent} />
    </div>
  );
}

function TwinHeader({ temp, power, ramUsed, accent, mode, onModeChange }){
  return (
    <div style={{
      padding: "14px 22px",
      display: "flex", justifyContent: "space-between", alignItems: "center",
      borderBottom: "1px solid var(--line)",
      background: "var(--bg-2)",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <span style={{
          width: 8, height: 8, background: accent,
          boxShadow: `0 0 8px ${accent}`, animation: "pulse-dot 1.4s infinite",
        }} />
        <span className="eyebrow" style={{ fontSize: 10, color: accent }}>边缘节点-001 · 实时</span>
        <span className="mono" style={{ fontSize: 11, color: "var(--fg-2)" }}>
          Orange Pi 5 Plus · RK3588 16GB · 6 TOPS NPU · 8 ARM 核
        </span>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
        <ModeSwitch mode={mode} onChange={onModeChange} accent={accent} />
        <span style={{ width: 1, height: 20, background: "var(--line)" }} />
        <ChipStat label="芯片温度" value={`${temp.toFixed(1)}°`} color={temp > 70 ? "var(--warn)" : "var(--fg-1)"} />
        <ChipStat label="功耗"    value={`${power.toFixed(1)}W`} />
        <ChipStat label="LPDDR4"   value={`${ramUsed.toFixed(1)}/16 GB`} />
      </div>
    </div>
  );
}

function ModeSwitch({ mode, onChange, accent }){
  const opts = [
    { v: "product", l: "产品视图" },
    { v: "xray",    l: "透视视图" },
    { v: "trace",   l: "追踪视图" },
  ];
  return (
    <div style={{ display: "inline-flex", border: "1px solid var(--line)", background: "var(--bg-1)" }}>
      {opts.map(o => {
        const active = mode === o.v;
        return (
          <button key={o.v}
            onClick={() => onChange && onChange(o.v)}
            style={{
              padding: "5px 12px",
              fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.12em",
              fontWeight: 600, textTransform: "uppercase",
              background: active ? accent : "transparent",
              color: active ? "var(--bg)" : "var(--fg-2)",
              border: "none",
              borderRight: o.v !== "trace" ? "1px solid var(--line)" : "none",
              cursor: "pointer",
            }}>{o.l}</button>
        );
      })}
    </div>
  );
}

function ChipStat({ label, value, color = "var(--fg-1)" }){
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2 }}>
      <span className="eyebrow" style={{ fontSize: 9 }}>{label}</span>
      <span className="mono" style={{ fontSize: 12, color, fontWeight: 500 }}>{value}</span>
    </div>
  );
}

// ── SVG chip stage ────────────────────────────────────────────────────────
function ChipStage({ phase, npuLoads, cpuLoads, mode, showTraces, accent, ramUsed }){
  const W = 1280, H = mode === "product" ? 420 : 600;
  const c0Active = phase.stage === "core0";
  const c1Active = phase.stage === "core1";
  const c2Active = phase.stage === "core2";
  const captureActive = phase.stage === "capture";
  const uploadActive = phase.stage === "upload";

  const npuYBase = mode === "product" ? 130 : 140;

  return (
    <div style={{ position: "relative", padding: "8px 0" }}>
      {/* grid bg */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none",
        backgroundImage:
          "linear-gradient(rgba(255,255,255,0.018) 1px, transparent 1px)," +
          "linear-gradient(90deg, rgba(255,255,255,0.018) 1px, transparent 1px)",
        backgroundSize: "40px 40px",
      }} />

      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet"
           style={{ width: "100%", display: "block", height: "auto" }}>
        <defs>
          <linearGradient id="chip-fill-v4" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#15151c" />
            <stop offset="100%" stopColor="#0a0a10" />
          </linearGradient>
          <linearGradient id="cg0" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--core-0)" stopOpacity="0.42" />
            <stop offset="100%" stopColor="var(--core-0)" stopOpacity="0.06" />
          </linearGradient>
          <linearGradient id="cg1" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--core-1)" stopOpacity="0.42" />
            <stop offset="100%" stopColor="var(--core-1)" stopOpacity="0.06" />
          </linearGradient>
          <linearGradient id="cg2" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--core-2)" stopOpacity="0.42" />
            <stop offset="100%" stopColor="var(--core-2)" stopOpacity="0.06" />
          </linearGradient>
        </defs>

        {/* CAMERA */}
        <CameraBlock x={30} y={mode === "product" ? 175 : 250} active={captureActive} accent={accent} />

        {/* TraceLine left */}
        <TraceLine d={`M 170 ${mode === "product" ? 240 : 315} L 235 ${mode === "product" ? 240 : 315}`}
                   active={captureActive || c0Active} accent={accent} />
        {showTraces && mode === "trace" && captureActive && (
          <TracePacket d={`M 170 ${mode === "product" ? 240 : 315} L 235 ${mode === "product" ? 240 : 315}`} color={accent} />
        )}

        {/* CHIP PACKAGE */}
        <g>
          <rect x={235} y={mode === "product" ? 75 : 60}
                width={830} height={mode === "product" ? 330 : 510}
                fill="url(#chip-fill-v4)" stroke="var(--line-hot)" strokeWidth="1" rx={3} />
          <rect x={250} y={mode === "product" ? 88 : 75}
                width={800} height={mode === "product" ? 304 : 480}
                fill="none" stroke="var(--line-soft)" strokeDasharray="3 3" rx={2} />

          {/* package pins — only in non-product mode */}
          {mode !== "product" && Array.from({ length: 30 }, (_, i) => {
            const x = 260 + i * 26;
            return (
              <g key={i}>
                <line x1={x} y1={56}  x2={x} y2={60}  stroke="var(--fg-4)" strokeWidth="1.5" />
                <line x1={x} y1={570} x2={x} y2={574} stroke="var(--fg-4)" strokeWidth="1.5" />
              </g>
            );
          })}

          {/* silkscreen */}
          <text x={650} y={mode === "product" ? 105 : 100} textAnchor="middle"
                fontFamily="var(--font-sans)" fontSize="13" fontWeight="600" fill="var(--fg-1)" letterSpacing="0.20em">
            ROCKCHIP RK3588
          </text>
          <text x={650} y={mode === "product" ? 121 : 116} textAnchor="middle"
                fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">
            SoC · 8nm · 8 核 CPU · 3 核 NPU · Mali-G610 · 6 TOPS · 16GB LPDDR4
          </text>

          {/* NPU CLUSTER */}
          <text x={250} y={npuYBase - 12} fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">
            ── NPU 集群 ──────────────────────────────────────────
          </text>
          <NPUCore x={278} y={npuYBase} w={240} h={170}
                   active={c0Active} mode={mode}
                   color="var(--core-0)" gradId="cg0"
                   title="NPU.0" model="EfficientAD-S" task="异常检测"
                   load={npuLoads[0]} ms={STAGE_REAL_MS.core0}
                   detail="PDN · 256×256 · INT8" thru="≈ 208 fps" />
          <NPUCore x={528} y={npuYBase} w={240} h={170}
                   active={c1Active} mode={mode}
                   color="var(--core-1)" gradId="cg1"
                   title="NPU.1" model="FastSAM-s" task="分割掩码"
                   load={npuLoads[1]} ms={STAGE_REAL_MS.core1}
                   detail="YOLOv8-seg · 640×640 · INT8" thru="≈ 20 fps" />
          <NPUCore x={778} y={npuYBase} w={240} h={170}
                   active={c2Active} mode={mode}
                   color="var(--core-2)" gradId="cg2"
                   title="NPU.2" model="Qwen3-VL" task="VLM 描述"
                   load={npuLoads[2]} ms={STAGE_REAL_MS.core2}
                   detail="W8A8 · ctx 4096 · RKLLM" thru="≈ 0.43 fps" isBottleneck />

          {/* X-RAY layer — show ARM + Mali + LPDDR */}
          {mode !== "product" && (
            <>
              <text x={250} y={340} fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">
                ── ARM 集群 ──────────────────────────────────────────
              </text>
              {[0, 1, 2, 3].map(i => (
                <CpuTile key={`a76_${i}`} x={278 + i * 92} y={350} w={84} h={68}
                         label={`A76·${i}`} freq="2.4G" load={cpuLoads[i]} kind="perf" />
              ))}
              <line x1={655} y1={350} x2={655} y2={418} stroke="var(--line-soft)" strokeDasharray="2 3" />
              {[0, 1, 2, 3].map(i => (
                <CpuTile key={`a55_${i}`} x={660 + i * 76} y={350} w={68} h={68}
                         label={`A55·${i}`} freq="1.8G" load={cpuLoads[4 + i]} kind="eff" />
              ))}
              <MaliGPU x={970} y={350} w={92} h={68} />

              <text x={250} y={448} fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">
                ── 共享内存 ──────────────────────────────────────────
              </text>
              <g>
                <rect x={278} y={458} width={784} height={56} fill="var(--bg-3)" stroke="var(--line)" />
                <text x={290} y={478} fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">
                  LPDDR4X · 16 GB · 64 位 · 4266 MT/s
                </text>
                <rect x={290} y={488} width={760} height={8} fill="var(--bg-4)" />
                <rect x={290} y={488} width={760 * (ramUsed/16)} height={8} fill={accent} opacity="0.78" />
                <text x={290 + 760 * (ramUsed/16) - 4} y={510} textAnchor="end"
                      fontFamily="var(--font-mono)" fontSize="8" fill="var(--fg-2)">
                  VLM 3.1G · 模型 4.8G · 运行时 1.3G
                </text>
                <text x={1050} y={478} textAnchor="end"
                      fontFamily="var(--font-mono)" fontSize="10" fill="var(--fg-1)">
                  {ramUsed.toFixed(1)} / 16.0 GB
                </text>
              </g>
            </>
          )}
        </g>

        {/* TraceLine right */}
        <TraceLine d={`M 1065 ${mode === "product" ? 240 : 315} L 1130 ${mode === "product" ? 240 : 315}`}
                   active={uploadActive} accent={accent} />
        {showTraces && mode === "trace" && uploadActive && (
          <TracePacket d={`M 1065 ${mode === "product" ? 240 : 315} L 1130 ${mode === "product" ? 240 : 315}`} color={accent} />
        )}

        {/* UPLINK */}
        <UploadBlock x={1130} y={mode === "product" ? 175 : 250} active={uploadActive} accent={accent} />
      </svg>
    </div>
  );
}

// ── Building blocks ──────────────────────────────────────────────────────
function CameraBlock({ x, y, active, accent }){
  return (
    <g>
      <rect x={x} y={y} width={140} height={130} fill="var(--bg-2)" stroke="var(--line)" />
      <text x={x+70} y={y+23} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">输入</text>
      <circle cx={x+70} cy={y+60} r={26} fill="none" stroke={active ? accent : "var(--fg-3)"} strokeWidth="1.5"
              style={active ? { filter: `drop-shadow(0 0 6px ${accent})` } : {}} />
      <circle cx={x+70} cy={y+60} r={14} fill="none" stroke={active ? accent : "var(--fg-3)"} strokeWidth="1" />
      <circle cx={x+70} cy={y+60} r={4}  fill={active ? accent : "var(--fg-3)"} />
      {active && (
        <circle cx={x+70} cy={y+60} r={26} fill="none" stroke={accent} strokeWidth="1"
                style={{ transformOrigin: `${x+70}px ${y+60}px`, animation: "ring-expand 1.2s ease-out infinite" }} />
      )}
      <text x={x+70} y={y+112} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="10" fill="var(--fg-1)">V4L2 · MJPEG</text>
      <text x={x+70} y={y+125} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)">1280×1280 · 30 fps</text>
    </g>
  );
}

function UploadBlock({ x, y, active, accent }){
  return (
    <g>
      <rect x={x} y={y} width={140} height={130} fill="var(--bg-2)" stroke="var(--line)" />
      <text x={x+70} y={y+23} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">上行</text>
      <g transform={`translate(${x+45}, ${y+42})`}>
        <rect x={0} y={0}  width={50} height={12} fill="none" stroke={active ? accent : "var(--fg-3)"} />
        <rect x={0} y={14} width={50} height={12} fill="none" stroke={active ? accent : "var(--fg-3)"} />
        <rect x={0} y={28} width={50} height={12} fill="none" stroke={active ? accent : "var(--fg-3)"} />
        <circle cx={6} cy={6}  r={1.5} fill={active ? accent : "var(--fg-3)"} />
        <circle cx={6} cy={20} r={1.5} fill={active ? accent : "var(--fg-3)"} />
        <circle cx={6} cy={34} r={1.5} fill={active ? accent : "var(--fg-3)"}
                style={active ? { animation: "pulse-dot 0.6s infinite" } : {}} />
      </g>
      <text x={x+70} y={y+108} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="10" fill="var(--fg-1)">FastAPI · POST</text>
      <text x={x+70} y={y+121} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)">/api/edge/report</text>
    </g>
  );
}

// ── NPU core tile — mode-aware density ───────────────────────────────────
function NPUCore({ x, y, w, h, active, mode, color, gradId, title, model, task, load, ms, detail, thru, isBottleneck }){
  const dense = mode !== "product";
  return (
    <g>
      <rect x={x} y={y} width={w} height={h}
            fill="var(--bg-2)" stroke={active ? color : "var(--line)"} strokeWidth={active ? 1.5 : 1} />
      {active && <rect x={x} y={y} width={w} height={h} fill={`url(#${gradId})`} />}
      {[[x, y, x+8, y, x, y+8],
        [x+w, y, x+w-8, y, x+w, y+8],
        [x, y+h, x+8, y+h, x, y+h-8],
        [x+w, y+h, x+w-8, y+h, x+w, y+h-8]].map((p, i) => (
        <polyline key={i} points={`${p[2]},${p[3]} ${p[0]},${p[1]} ${p[4]},${p[5]}`}
                  fill="none" stroke={active ? color : "var(--fg-4)"} strokeWidth="1" />
      ))}
      <rect x={x} y={y} width={w} height={20} fill={active ? `color-mix(in srgb, ${color} 22%, transparent)` : "var(--bg-3)"} />
      <text x={x+10} y={y+14} fontFamily="var(--font-mono)" fontSize="9"
            fill={active ? color : "var(--fg-3)"} letterSpacing="0.12em">{title}</text>
      {active && (
        <circle cx={x+w-12} cy={y+10} r={3} fill={color} style={{ animation: "pulse-dot 0.8s infinite" }} />
      )}
      {isBottleneck && !active && (
        <text x={x+w-10} y={y+14} textAnchor="end"
              fontFamily="var(--font-mono)" fontSize="8" fill="var(--core-2)" letterSpacing="0.1em">瓶颈</text>
      )}

      <text x={x+w/2} y={y+44} textAnchor="middle"
            fontFamily="var(--font-sans)" fontSize="16" fontWeight="600"
            fill={active ? "var(--fg)" : "var(--fg-1)"}>{model}</text>
      <text x={x+w/2} y={y+60} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.1em">
        {task}
      </text>

      <text x={x+w/2} y={y+100} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="30" fontWeight="500"
            fill={color}
            style={active ? { filter: `drop-shadow(0 0 8px ${color})` } : {}}>
        {ms < 100 ? ms.toFixed(1) : Math.round(ms)}
        <tspan fontSize="13" fill="var(--fg-3)" dx="2">ms p50</tspan>
      </text>

      {dense && (
        <g transform={`translate(${x+14}, ${y+122})`}>
          <text x={0} y={0} fontFamily="var(--font-mono)" fontSize="8" fill="var(--fg-3)" letterSpacing="0.1em">负载</text>
          <text x={w-28} y={0} textAnchor="end" fontFamily="var(--font-mono)" fontSize="10" fill={color} fontWeight="600">
            {Math.round(load)}%
          </text>
          <rect x={0} y={6} width={w-28} height={4} fill="var(--bg-4)" />
          <rect x={0} y={6} width={(w-28) * (load / 100)} height={4} fill={color}
                style={active ? { filter: `drop-shadow(0 0 4px ${color})` } : {}} />
        </g>
      )}

      {dense && (
        <>
          <text x={x+14} y={y+h-14} fontFamily="var(--font-mono)" fontSize="8" fill="var(--fg-3)">{detail}</text>
          <text x={x+w-14} y={y+h-14} textAnchor="end" fontFamily="var(--font-mono)" fontSize="8" fill="var(--fg-2)">{thru}</text>
        </>
      )}
      {!dense && (
        <text x={x+w/2} y={y+h-16} textAnchor="middle"
              fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.08em">{detail}</text>
      )}
    </g>
  );
}

function CpuTile({ x, y, w, h, label, freq, load, kind }){
  const color = kind === "perf" ? "var(--core-0)" : "var(--fg-2)";
  const isHot = load > 60;
  return (
    <g>
      <rect x={x} y={y} width={w} height={h}
            fill={isHot ? `color-mix(in srgb, ${color} 18%, var(--bg-3))` : "var(--bg-3)"}
            stroke={isHot ? color : "var(--line)"} strokeWidth={isHot ? 1 : 0.8} />
      <circle cx={x+4} cy={y+4} r={1.5} fill={kind === "perf" ? "var(--core-0)" : "var(--fg-3)"} opacity={0.8} />
      <text x={x+w/2} y={y+14} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-1)" fontWeight="600">{label}</text>
      <text x={x+w/2} y={y+25} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="7" fill="var(--fg-3)">{freq}Hz</text>
      <text x={x+w/2} y={y+45} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="15" fontWeight="500"
            fill={isHot ? color : "var(--fg-2)"}
            style={isHot ? { filter: `drop-shadow(0 0 4px ${color})` } : {}}>
        {Math.round(load)}<tspan fontSize="8" fill="var(--fg-3)" dx="0.5">%</tspan>
      </text>
      <rect x={x+6} y={y+h-8} width={w-12} height={2} fill="var(--bg-4)" />
      <rect x={x+6} y={y+h-8} width={(w-12) * (load/100)} height={2} fill={color} />
    </g>
  );
}

function MaliGPU({ x, y, w, h }){
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} fill="var(--bg-3)" stroke="var(--line)" />
      <text x={x+w/2} y={y+14} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-1)" fontWeight="600">Mali-G610</text>
      <text x={x+w/2} y={y+25} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="7" fill="var(--fg-3)">MP4 · OpenCL</text>
      <text x={x+w/2} y={y+45} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="14" fontWeight="500" fill="var(--fg-3)">空闲</text>
      <text x={x+w/2} y={y+h-8} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="7" fill="var(--fg-3)">RGA 优先</text>
    </g>
  );
}

function TraceLine({ d, active, accent }){
  return (
    <g>
      <path d={d} stroke="var(--line-hot)" strokeWidth="1.5" fill="none" strokeDasharray="3 4" />
      {active && <path d={d} stroke={accent} strokeWidth="1.5" fill="none"
                       style={{ filter: `drop-shadow(0 0 4px ${accent})` }} />}
    </g>
  );
}
function TracePacket({ d, color }){
  return (
    <g>
      {[0, 1, 2].map(i => (
        <circle key={i} r="3" fill={color}
                style={{
                  offsetPath: `path("${d}")`,
                  offsetDistance: "0%",
                  animation: `packet-flow 0.8s linear ${i * 0.22}s infinite`,
                  filter: `drop-shadow(0 0 4px ${color})`,
                }} />
      ))}
    </g>
  );
}

// ── Frame Journey rail (bottom of hero) ──────────────────────────────────
function FrameJourney({ phase, accent }){
  const nodes = [
    { stage: "capture", label: "摄像头",       out: "frame",          color: accent },
    { stage: "core0",   label: "EfficientAD-S",out: "anomaly_score",  color: "var(--core-0)" },
    { stage: "core1",   label: "FastSAM-s",    out: "bboxes + mask",  color: "var(--core-1)" },
    { stage: "core2",   label: "Qwen3-VL",     out: "JSON",           color: "var(--core-2)" },
    { stage: "upload",  label: "上行",       out: "POST /api/edge/report", color: accent },
  ];
  return (
    <div style={{
      borderTop: "1px solid var(--line)",
      padding: "16px 22px",
      display: "grid", gridTemplateColumns: `repeat(${nodes.length}, 1fr) auto`, gap: 0, alignItems: "stretch",
      background: "var(--bg-2)",
    }}>
      {nodes.map((n, i) => {
        const active = phase.stage === n.stage;
        return (
          <React.Fragment key={n.stage}>
            <div style={{ display: "flex", flexDirection: "column", gap: 4, paddingRight: 14, position: "relative" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{
                  width: 8, height: 8, background: active ? n.color : "var(--fg-4)",
                  boxShadow: active ? `0 0 6px ${n.color}` : "none",
                }} />
                <span className="mono" style={{
                  fontSize: 10, color: active ? n.color : "var(--fg-2)",
                  letterSpacing: "0.12em", fontWeight: 600, textTransform: "uppercase",
                }}>{n.label}</span>
              </div>
              <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", paddingLeft: 16 }}>
                → {n.out}
              </span>
              {i < nodes.length - 1 && (
                <span style={{
                  position: "absolute", right: 0, top: 6, height: 1, width: 14,
                  background: "var(--line-hot)",
                }} />
              )}
            </div>
          </React.Fragment>
        );
      })}
      <div style={{ display: "flex", alignItems: "center", gap: 10, paddingLeft: 18,
                    borderLeft: "1px solid var(--line)" }}>
        <span className="eyebrow">当前帧</span>
        <span className="mono" style={{ fontSize: 12, color: "var(--fg)" }}>{phase.frameId ?? "—"}</span>
      </div>
    </div>
  );
}

Object.assign(window, { RK3588Twin, useFrameSimulator, useCpuLoads });
