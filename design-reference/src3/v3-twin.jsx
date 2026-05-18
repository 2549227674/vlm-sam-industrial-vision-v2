// RK3588 Digital Twin — chip-centric SVG with 3 NPU cores, 4×A76 + 4×A55 CPU cluster,
// Mali-G610 GPU, LPDDR4 memory, animated dataflow packets.

const { useState: _twS, useEffect: _twE, useMemo: _twM, useRef: _twR } = React;

// Stage scaling for the visualization (real ms are 5/50/2300 — too uneven to watch live)
const STAGE_DURATIONS_MS = { capture: 300, core0: 280, core1: 480, core2: 1700, upload: 320, idle: 380 };
const STAGE_REAL_MS = { core0: 4.8, core1: 50, core2: 2300 };

function useFrameSimulator({ live, speed = 1, onComplete }){
  const [phase, setPhase] = _twS({ stage: "idle", frameId: null, startedAt: 0 });
  const tRef = _twR();
  const speedRef = _twR(speed);
  speedRef.current = speed;

  _twE(() => {
    if (!live) return;
    let cancelled = false;

    function transition(nextStage, frameId, delay){
      tRef.current = setTimeout(() => {
        if (cancelled) return;
        setPhase({ stage: nextStage, frameId, startedAt: performance.now() });
        const scale = speedRef.current > 0 ? 1 / speedRef.current : 1;
        if (nextStage === "idle"){
          if (onComplete) onComplete(frameId);
          transition("capture", `F-${Date.now().toString().slice(-5)}`, STAGE_DURATIONS_MS.idle * scale);
        } else if (nextStage === "capture") transition("core0", frameId, STAGE_DURATIONS_MS.capture * scale);
        else if (nextStage === "core0")     transition("core1", frameId, STAGE_DURATIONS_MS.core0 * scale);
        else if (nextStage === "core1")     transition("core2", frameId, STAGE_DURATIONS_MS.core1 * scale);
        else if (nextStage === "core2")     transition("upload", frameId, STAGE_DURATIONS_MS.core2 * scale);
        else if (nextStage === "upload")    transition("idle",   frameId, STAGE_DURATIONS_MS.upload * scale);
      }, delay);
    }
    transition("capture", `F-${Date.now().toString().slice(-5)}`, 200);
    return () => { cancelled = true; clearTimeout(tRef.current); };
  }, [live]);

  return phase;
}

// ── CPU cluster simulator ────────────────────────────────────────────────────
function useCpuLoads({ phase, speed = 1 }){
  // Returns 8 cores: [a76_0..3, a55_0..3] with load %
  // Loads correlate with stage: A76_0 handles EfficientAD postproc, A76_1 handles bbox NMS,
  // A76_2 handles VLM sampling, A76_3 is general, A55s do scheduling/IO
  const [loads, setLoads] = _twS(() => [22, 14, 36, 18, 8, 6, 9, 5]);
  _twE(() => {
    const id = setInterval(() => {
      setLoads(prev => prev.map((v, i) => {
        let target = v;
        // bias by stage
        if (phase.stage === "core0" && i === 0) target = 65;
        else if (phase.stage === "core1" && i === 1) target = 72;
        else if (phase.stage === "core2" && i === 2) target = 88;
        else if (phase.stage === "upload" && i === 4) target = 42;
        else target = i < 4 ? 18 + Math.random() * 16 : 5 + Math.random() * 12;
        // smooth towards target
        return Math.max(0, Math.min(100, v + (target - v) * 0.35 + (Math.random() - 0.5) * 6));
      }));
    }, 600 / Math.max(speed, 0.25));
    return () => clearInterval(id);
  }, [phase.stage, speed]);
  return loads;
}

function RK3588Twin({ phase, npuLoads, cpuLoads, temp = 62.4, power = 4.8, ramUsed = 9.2, showTraces = true, accent = "var(--acc)" }){
  const W = 1280, H = 600;
  const c0Active = phase.stage === "core0";
  const c1Active = phase.stage === "core1";
  const c2Active = phase.stage === "core2";
  const captureActive = phase.stage === "capture";
  const uploadActive = phase.stage === "upload";

  return (
    <div style={{
      position: "relative", width: "100%",
      background: "var(--bg-1)",
      border: "1px solid var(--line)",
      overflow: "hidden",
    }}>
      {/* Grid bg */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none",
        backgroundImage:
          "linear-gradient(rgba(255,255,255,0.018) 1px, transparent 1px), " +
          "linear-gradient(90deg, rgba(255,255,255,0.018) 1px, transparent 1px)",
        backgroundSize: "40px 40px",
      }} />

      {/* Header tape */}
      <div style={{
        position: "relative", padding: "14px 22px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        borderBottom: "1px solid var(--line-soft)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <span style={{
            width: 8, height: 8, background: accent, borderRadius: "50%",
            boxShadow: `0 0 8px ${accent}`, animation: "pulse-dot 1.4s infinite",
          }} />
          <span className="eyebrow" style={{ fontSize: 10, color: accent }}>EDGE.NODE-001 · LIVE</span>
          <span className="mono" style={{ fontSize: 11, color: "var(--fg-2)" }}>
            Orange Pi 5 Plus · RK3588 16GB · 6 TOPS NPU · 8 ARM cores
          </span>
        </div>
        <div style={{ display: "flex", gap: 22 }}>
          <ChipStat label="SoC TEMP" value={`${temp.toFixed(1)}°`} color={temp > 70 ? "var(--warn)" : "var(--fg-1)"} />
          <ChipStat label="POWER"    value={`${power.toFixed(1)}W`} />
          <ChipStat label="LPDDR4"   value={`${ramUsed.toFixed(1)}/16 GB`} />
          <ChipStat label="UPTIME"   value="3d 14h" />
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet"
           style={{ width: "100%", display: "block", height: "auto" }}>
        <defs>
          <linearGradient id="chip-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#1c1c25" />
            <stop offset="100%" stopColor="#0e0e15" />
          </linearGradient>
          <linearGradient id="core-active-0" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--core-0)" stopOpacity="0.42" />
            <stop offset="100%" stopColor="var(--core-0)" stopOpacity="0.06" />
          </linearGradient>
          <linearGradient id="core-active-1" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--core-1)" stopOpacity="0.42" />
            <stop offset="100%" stopColor="var(--core-1)" stopOpacity="0.06" />
          </linearGradient>
          <linearGradient id="core-active-2" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--core-2)" stopOpacity="0.42" />
            <stop offset="100%" stopColor="var(--core-2)" stopOpacity="0.06" />
          </linearGradient>
        </defs>

        {/* ============== CAMERA (left) ============== */}
        <g>
          <rect x={30} y={250} width={140} height={130} fill="var(--bg-2)" stroke="var(--line)" />
          <text x={100} y={273} textAnchor="middle"
                fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">INGEST</text>
          <circle cx={100} cy={310} r={26} fill="none" stroke={captureActive ? accent : "var(--fg-3)"} strokeWidth="1.5"
                  style={captureActive ? { filter: `drop-shadow(0 0 6px ${accent})` } : {}} />
          <circle cx={100} cy={310} r={14} fill="none" stroke={captureActive ? accent : "var(--fg-3)"} strokeWidth="1" />
          <circle cx={100} cy={310} r={4}  fill={captureActive ? accent : "var(--fg-3)"} />
          {captureActive && (
            <circle cx={100} cy={310} r={26} fill="none" stroke={accent} strokeWidth="1"
                    style={{ transformOrigin: "100px 310px", animation: "ring-expand 1.2s ease-out infinite" }} />
          )}
          <text x={100} y={362} textAnchor="middle"
                fontFamily="var(--font-mono)" fontSize="10" fill="var(--fg-1)">V4L2 · MJPEG</text>
          <text x={100} y={375} textAnchor="middle"
                fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)">1280×1280 · 30 fps</text>
        </g>

        {/* trace */}
        <TraceLine d="M 170 315 L 235 315" active={captureActive || c0Active} accent={accent} />
        {showTraces && captureActive && <TracePacket d="M 170 315 L 235 315" color={accent} />}

        {/* ============== CHIP PACKAGE ============== */}
        <g>
          <rect x={235} y={60} width={830} height={510}
                fill="url(#chip-fill)" stroke="var(--line-hot)" strokeWidth="1" rx={4} />
          <rect x={250} y={75} width={800} height={480}
                fill="none" stroke="var(--line-soft)" strokeDasharray="3 3" rx={2} />

          {/* package pins */}
          {Array.from({ length: 30 }, (_, i) => {
            const x = 260 + i * 26;
            return (
              <g key={i}>
                <line x1={x} y1={56}  x2={x} y2={60}  stroke="var(--fg-4)" strokeWidth="1.5" />
                <line x1={x} y1={570} x2={x} y2={574} stroke="var(--fg-4)" strokeWidth="1.5" />
              </g>
            );
          })}

          {/* silkscreen */}
          <text x={650} y={92} textAnchor="middle"
                fontFamily="var(--font-sans)" fontSize="14" fontWeight="600" fill="var(--fg-1)" letterSpacing="0.18em">
            ROCKCHIP RK3588
          </text>
          <text x={650} y={108} textAnchor="middle"
                fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.16em">
            SoC · 8nm · 8-core CPU · 3-core NPU · Mali-G610 · 6 TOPS
          </text>

          {/* ============== 3 NPU CORES (top tier) ============== */}
          <text x={250} y={130} fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">
            ── NPU CLUSTER ──────────────────────────────────────────────────
          </text>
          <NPUCore x={278} y={140} w={240} h={170}
                   active={c0Active}
                   color="var(--core-0)" gradId="core-active-0"
                   title="NPU CORE 0"
                   model="EfficientAD-S"
                   task="Anomaly Detection"
                   load={npuLoads[0]}
                   ms={STAGE_REAL_MS.core0}
                   detail="PDN · 256×256 · INT8"
                   thru="≈ 208 fps" />
          <NPUCore x={528} y={140} w={240} h={170}
                   active={c1Active}
                   color="var(--core-1)" gradId="core-active-1"
                   title="NPU CORE 1"
                   model="FastSAM-s"
                   task="Segment Mask"
                   load={npuLoads[1]}
                   ms={STAGE_REAL_MS.core1}
                   detail="YOLOv8-seg · 640×640 · INT8"
                   thru="≈ 20 fps" />
          <NPUCore x={778} y={140} w={240} h={170}
                   active={c2Active}
                   color="var(--core-2)" gradId="core-active-2"
                   title="NPU CORE 2"
                   model="Qwen3-VL-2B"
                   task="VLM Describe"
                   load={npuLoads[2]}
                   ms={STAGE_REAL_MS.core2}
                   detail="W8A8 · ctx 4096 · RKLLM"
                   thru="≈ 0.43 fps"
                   isBottleneck />

          {/* ============== CPU CLUSTER (middle tier) ============== */}
          <text x={250} y={340} fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">
            ── ARM CLUSTER ──────────────────────────────────────────────────
          </text>
          {/* A76 ×4 — bigger, performance cores */}
          {[0, 1, 2, 3].map(i => (
            <CpuTile key={`a76_${i}`}
                     x={278 + i * 92} y={350} w={84} h={68}
                     label={`A76·${i}`}
                     freq="2.4G"
                     load={cpuLoads[i]}
                     kind="perf" />
          ))}
          {/* divider */}
          <line x1={655} y1={350} x2={655} y2={418} stroke="var(--line-soft)" strokeDasharray="2 3" />
          {/* A55 ×4 — efficiency cores */}
          {[0, 1, 2, 3].map(i => (
            <CpuTile key={`a55_${i}`}
                     x={660 + i * 76} y={350} w={68} h={68}
                     label={`A55·${i}`}
                     freq="1.8G"
                     load={cpuLoads[4 + i]}
                     kind="eff" />
          ))}
          {/* Mali GPU */}
          <MaliGPU x={970} y={350} w={92} h={68} />

          {/* ============== LPDDR4 strip (bottom tier) ============== */}
          <text x={250} y={448} fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">
            ── SHARED MEMORY ────────────────────────────────────────────────
          </text>
          <g>
            <rect x={278} y={458} width={784} height={56} fill="var(--bg-3)" stroke="var(--line)" />
            <text x={290} y={478} fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">
              LPDDR4X · 16 GB · 64-bit · 4266 MT/s
            </text>
            <rect x={290} y={488} width={760} height={8} fill="var(--bg-4)" />
            <rect x={290} y={488} width={760 * (ramUsed/16)} height={8} fill={accent} opacity="0.75"
                  style={{ filter: `drop-shadow(0 0 6px ${accent})` }} />
            {/* memory regions */}
            <text x={290 + 760 * (ramUsed/16) - 4} y={510} textAnchor="end"
                  fontFamily="var(--font-mono)" fontSize="8" fill="var(--fg-2)">
              VLM 3.1G · models 4.8G · runtime 1.3G
            </text>
            <text x={1050} y={478} textAnchor="end"
                  fontFamily="var(--font-mono)" fontSize="10" fill="var(--fg-1)">
              {ramUsed.toFixed(1)} / 16.0 GB
            </text>
          </g>

          {/* footer info */}
          <text x={278} y={547} fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-4)" letterSpacing="0.06em">
            RK3588 die · package BGA-588 · TSMC 8nm · TDP 5W
          </text>
        </g>

        {/* trace right */}
        <TraceLine d="M 1065 315 L 1130 315" active={uploadActive} accent={accent} />
        {showTraces && uploadActive && <TracePacket d="M 1065 315 L 1130 315" color={accent} />}

        {/* ============== UPLOAD/CLOUD ============== */}
        <g>
          <rect x={1130} y={250} width={140} height={130} fill="var(--bg-2)" stroke="var(--line)" />
          <text x={1200} y={273} textAnchor="middle"
                fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">UPLINK</text>
          <g transform="translate(1175, 292)">
            <rect x={0} y={0}  width={50} height={12} fill="none" stroke={uploadActive ? accent : "var(--fg-3)"} />
            <rect x={0} y={14} width={50} height={12} fill="none" stroke={uploadActive ? accent : "var(--fg-3)"} />
            <rect x={0} y={28} width={50} height={12} fill="none" stroke={uploadActive ? accent : "var(--fg-3)"} />
            <circle cx={6} cy={6}  r={1.5} fill={uploadActive ? accent : "var(--fg-3)"} />
            <circle cx={6} cy={20} r={1.5} fill={uploadActive ? accent : "var(--fg-3)"} />
            <circle cx={6} cy={34} r={1.5} fill={uploadActive ? accent : "var(--fg-3)"}
                    style={uploadActive ? { animation: "pulse-dot 0.6s infinite" } : {}} />
          </g>
          <text x={1200} y={358} textAnchor="middle"
                fontFamily="var(--font-mono)" fontSize="10" fill="var(--fg-1)">POST · multipart</text>
          <text x={1200} y={371} textAnchor="middle"
                fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)">/api/edge/report</text>
        </g>
      </svg>

      {/* Bottom ticker */}
      <FrameTickerBar phase={phase} accent={accent} />
    </div>
  );
}

// ── NPU core tile ────────────────────────────────────────────────────────────
function NPUCore({ x, y, w, h, active, color, gradId, title, model, task, load, ms, detail, thru, isBottleneck }){
  return (
    <g>
      <rect x={x} y={y} width={w} height={h}
            fill="var(--bg-2)" stroke={active ? color : "var(--line)"} strokeWidth={active ? 1.5 : 1} />
      {active && <rect x={x} y={y} width={w} height={h} fill={`url(#${gradId})`} />}
      {/* corner ticks */}
      {[[x, y, x+8, y, x, y+8],
        [x+w, y, x+w-8, y, x+w, y+8],
        [x, y+h, x+8, y+h, x, y+h-8],
        [x+w, y+h, x+w-8, y+h, x+w, y+h-8]].map((p, i) => (
        <polyline key={i} points={`${p[2]},${p[3]} ${p[0]},${p[1]} ${p[4]},${p[5]}`}
                  fill="none" stroke={active ? color : "var(--fg-4)"} strokeWidth="1" />
      ))}
      <rect x={x} y={y} width={w} height={20} fill={active ? `color-mix(in srgb, ${color} 22%, transparent)` : "var(--bg-3)"} />
      <text x={x + 10} y={y + 14} fontFamily="var(--font-mono)" fontSize="9"
            fill={active ? color : "var(--fg-3)"} letterSpacing="0.12em">{title}</text>
      {active && (
        <circle cx={x + w - 12} cy={y + 10} r={3} fill={color}
                style={{ animation: "pulse-dot 0.8s infinite" }} />
      )}
      {isBottleneck && !active && (
        <text x={x + w - 10} y={y + 14} textAnchor="end"
              fontFamily="var(--font-mono)" fontSize="8" fill="var(--core-2)" letterSpacing="0.1em">HOT</text>
      )}

      <text x={x + w/2} y={y + 44} textAnchor="middle"
            fontFamily="var(--font-sans)" fontSize="16" fontWeight="600"
            fill={active ? "var(--fg)" : "var(--fg-1)"}>{model}</text>
      <text x={x + w/2} y={y + 60} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.1em">
        {task.toUpperCase()}
      </text>

      <text x={x + w/2} y={y + 100} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="30" fontWeight="500"
            fill={color}
            style={active ? { filter: `drop-shadow(0 0 8px ${color})` } : {}}>
        {ms < 100 ? ms.toFixed(1) : Math.round(ms)}
        <tspan fontSize="13" fill="var(--fg-3)" dx="2">ms</tspan>
      </text>

      <g transform={`translate(${x + 14}, ${y + 122})`}>
        <text x={0} y={0} fontFamily="var(--font-mono)" fontSize="8" fill="var(--fg-3)" letterSpacing="0.1em">LOAD</text>
        <text x={w - 28} y={0} textAnchor="end" fontFamily="var(--font-mono)" fontSize="10" fill={color} fontWeight="600">
          {Math.round(load)}%
        </text>
        <rect x={0} y={6} width={w - 28} height={4} fill="var(--bg-4)" />
        <rect x={0} y={6} width={(w - 28) * (load / 100)} height={4} fill={color}
              style={active ? { filter: `drop-shadow(0 0 4px ${color})` } : {}} />
      </g>

      <text x={x + 14} y={y + h - 14} fontFamily="var(--font-mono)" fontSize="8" fill="var(--fg-3)">{detail}</text>
      <text x={x + w - 14} y={y + h - 14} textAnchor="end" fontFamily="var(--font-mono)" fontSize="8" fill="var(--fg-2)">{thru}</text>
    </g>
  );
}

// ── CPU core tile ────────────────────────────────────────────────────────────
function CpuTile({ x, y, w, h, label, freq, load, kind }){
  const color = kind === "perf" ? "var(--core-0)" : "var(--fg-2)";
  const isHot = load > 60;
  return (
    <g>
      <rect x={x} y={y} width={w} height={h}
            fill={isHot ? `color-mix(in srgb, ${color} 18%, var(--bg-3))` : "var(--bg-3)"}
            stroke={isHot ? color : "var(--line)"} strokeWidth={isHot ? 1 : 0.8} />
      {/* corner pip */}
      <circle cx={x + 4} cy={y + 4} r={1.5} fill={kind === "perf" ? "var(--core-0)" : "var(--fg-3)"} opacity={0.8} />
      {/* label */}
      <text x={x + w/2} y={y + 14} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-1)" fontWeight="600">{label}</text>
      <text x={x + w/2} y={y + 25} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="7" fill="var(--fg-3)">{freq}Hz</text>
      {/* big % */}
      <text x={x + w/2} y={y + 45} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="15" fontWeight="500"
            fill={isHot ? color : "var(--fg-2)"}
            style={isHot ? { filter: `drop-shadow(0 0 4px ${color})` } : {}}>
        {Math.round(load)}<tspan fontSize="8" fill="var(--fg-3)" dx="0.5">%</tspan>
      </text>
      {/* mini bar */}
      <rect x={x + 6} y={y + h - 8} width={w - 12} height={2} fill="var(--bg-4)" />
      <rect x={x + 6} y={y + h - 8} width={(w - 12) * (load / 100)} height={2} fill={color} />
    </g>
  );
}

function MaliGPU({ x, y, w, h }){
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} fill="var(--bg-3)" stroke="var(--line)" />
      <text x={x + w/2} y={y + 14} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-1)" fontWeight="600">Mali-G610</text>
      <text x={x + w/2} y={y + 25} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="7" fill="var(--fg-3)">MP4 · OpenCL</text>
      <text x={x + w/2} y={y + 45} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="14" fontWeight="500" fill="var(--fg-3)">
        IDLE
      </text>
      <text x={x + w/2} y={y + h - 8} textAnchor="middle"
            fontFamily="var(--font-mono)" fontSize="7" fill="var(--fg-3)">RGA preferred</text>
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

function ChipStat({ label, value, color = "var(--fg-1)" }){
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2 }}>
      <span className="eyebrow" style={{ fontSize: 9 }}>{label}</span>
      <span className="mono" style={{ fontSize: 13, color, fontWeight: 500 }}>{value}</span>
    </div>
  );
}

function FrameTickerBar({ phase, accent = "var(--acc)" }){
  const stageLabel = {
    capture: { name: "Capturing frame · V4L2 ioctl", color: accent },
    core0:   { name: "EfficientAD · Stage 1/3 · NPU0", color: "var(--core-0)" },
    core1:   { name: "FastSAM · Stage 2/3 · NPU1",     color: "var(--core-1)" },
    core2:   { name: "Qwen3-VL · Stage 3/3 · NPU2 · Decoding", color: "var(--core-2)" },
    upload:  { name: "POST /api/edge/report · multipart",    color: accent },
    idle:    { name: "Pipeline ready",          color: "var(--fg-2)" },
  }[phase.stage] || { name: "—", color: "var(--fg-2)" };

  return (
    <div style={{
      padding: "12px 22px",
      borderTop: "1px solid var(--line-soft)",
      display: "flex", justifyContent: "space-between", alignItems: "center",
      background: "var(--bg-2)",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <span style={{
          width: 8, height: 8, borderRadius: "50%", background: stageLabel.color,
          boxShadow: `0 0 6px ${stageLabel.color}`,
          animation: phase.stage !== "idle" ? "pulse-dot 0.8s infinite" : "none",
        }} />
        <span className="eyebrow">CURRENT FRAME</span>
        <span className="mono" style={{ fontSize: 12, color: "var(--fg-1)" }}>{phase.frameId ?? "—"}</span>
        <span style={{ width: 1, height: 14, background: "var(--line)" }} />
        <span className="mono" style={{ fontSize: 12, color: stageLabel.color, fontWeight: 500 }}>
          {stageLabel.name}<BlinkCursor color={stageLabel.color} />
        </span>
      </div>
      <div style={{ display: "flex", gap: 22 }}>
        <ChipStat label="PIPELINE" value="Async · 4-thread (T1-T4)" />
        <ChipStat label="Σ E2E"    value="≈ 2.4 s/frame" />
      </div>
    </div>
  );
}

function BlinkCursor({ color }){
  return (
    <span style={{
      display: "inline-block", width: 6, height: 11, marginLeft: 6,
      background: color, verticalAlign: "middle",
      animation: "blink-cursor 1s infinite",
    }} />
  );
}

Object.assign(window, { RK3588Twin, useFrameSimulator, useCpuLoads });
