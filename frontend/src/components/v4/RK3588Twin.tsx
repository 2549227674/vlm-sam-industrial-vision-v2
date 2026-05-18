"use client";

import React, { useState, useEffect, useRef } from "react";

// ── Frame simulator hook ────────────────────────────────────────────────────

const STAGE_DURATIONS_MS = { capture: 320, core0: 280, core1: 480, core2: 1700, upload: 320, idle: 380 };
const STAGE_REAL_MS = { core0: 4.8, core1: 50, core2: 2300 };

export interface FramePhase {
  stage: string;
  frameId: string | null;
  startedAt: number;
}

export function useFrameSimulator({ live, onComplete }: { live: boolean; onComplete: () => void }) {
  const [phase, setPhase] = useState<FramePhase>({ stage: "idle", frameId: null, startedAt: 0 });
  const tRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const onCompRef = useRef(onComplete);
  onCompRef.current = onComplete;

  useEffect(() => {
    if (!live) return;
    let cancelled = false;
    function tx(next: string, frameId: string, delay: number) {
      tRef.current = setTimeout(() => {
        if (cancelled) return;
        setPhase({ stage: next, frameId, startedAt: performance.now() });
        if (next === "idle") {
          onCompRef.current();
          tx("capture", `F-${Date.now().toString().slice(-5)}`, STAGE_DURATIONS_MS.idle);
        } else if (next === "capture") tx("core0", frameId, STAGE_DURATIONS_MS.capture);
        else if (next === "core0") tx("core1", frameId, STAGE_DURATIONS_MS.core0);
        else if (next === "core1") tx("core2", frameId, STAGE_DURATIONS_MS.core1);
        else if (next === "core2") tx("upload", frameId, STAGE_DURATIONS_MS.core2);
        else if (next === "upload") tx("idle", frameId, STAGE_DURATIONS_MS.upload);
      }, delay);
    }
    tx("capture", `F-${Date.now().toString().slice(-5)}`, 200);
    return () => { cancelled = true; clearTimeout(tRef.current); };
  }, [live]);

  return phase;
}

// ── CPU loads hook ──────────────────────────────────────────────────────────

export function useCpuLoads(phase: FramePhase) {
  const [loads, setLoads] = useState(() => [22, 14, 36, 18, 8, 6, 9, 5]);
  useEffect(() => {
    const id = setInterval(() => {
      setLoads(prev => prev.map((v, i) => {
        let target: number;
        if (phase.stage === "core0" && i === 0) target = 65;
        else if (phase.stage === "core1" && i === 1) target = 72;
        else if (phase.stage === "core2" && i === 2) target = 88;
        else if (phase.stage === "upload" && i === 4) target = 42;
        else target = i < 4 ? 18 + Math.random() * 16 : 5 + Math.random() * 12;
        return Math.max(0, Math.min(100, v + (target - v) * 0.35 + (Math.random() - 0.5) * 6));
      }));
    }, 600);
    return () => clearInterval(id);
  }, [phase.stage]);
  return loads;
}

// ── NPU loads hook ──────────────────────────────────────────────────────────

export function useNpuLoads() {
  const [loads, setLoads] = useState([22, 41, 78]);
  useEffect(() => {
    const id = setInterval(() => {
      setLoads([
        Math.max(8, Math.min(35, 22 + (Math.random() - 0.5) * 14)),
        Math.max(20, Math.min(70, 41 + (Math.random() - 0.5) * 18)),
        Math.max(60, Math.min(95, 78 + (Math.random() - 0.5) * 12)),
      ]);
    }, 1200);
    return () => clearInterval(id);
  }, []);
  return loads;
}

// ── Top-level twin ──────────────────────────────────────────────────────────

interface TwinProps {
  phase: FramePhase;
  npuLoads: number[];
  cpuLoads: number[];
  mode: string;
  showTraces?: boolean;
  ramUsed: number;
  onModeChange?: (m: string) => void;
  accent?: string;
}

export function RK3588Twin({ phase, npuLoads, cpuLoads, mode, showTraces = true, ramUsed, onModeChange, accent = "var(--acc)" }: TwinProps) {
  const c0Active = phase.stage === "core0";
  const c1Active = phase.stage === "core1";
  const c2Active = phase.stage === "core2";
  const captureActive = phase.stage === "capture";
  const uploadActive = phase.stage === "upload";
  const dense = mode !== "product";
  const W = 1280, H = mode === "product" ? 420 : 600;
  const camY = mode === "product" ? 175 : 250;
  const chipY = mode === "product" ? 75 : 60;
  const chipH = mode === "product" ? 330 : 510;
  const innerY = mode === "product" ? 88 : 75;
  const innerH = mode === "product" ? 304 : 480;
  const npuY = mode === "product" ? 130 : 140;

  const modeOpts = [
    { v: "xray", l: "透视视图" },
    { v: "product", l: "产品视图" },
    { v: "trace", l: "追踪视图" },
  ];

  const journey = [
    { stage: "capture", label: "摄像头", out: "frame", color: accent },
    { stage: "core0", label: "EfficientAD-S", out: "anomaly_score", color: "var(--core-0)" },
    { stage: "core1", label: "FastSAM-s", out: "bboxes + mask", color: "var(--core-1)" },
    { stage: "core2", label: "Qwen3-VL", out: "JSON", color: "var(--core-2)" },
    { stage: "upload", label: "上行", out: "POST /api/edge/report", color: accent },
  ];

  return (
    <div style={{ position: "relative", width: "100%", background: "var(--bg-1)", border: "1px solid var(--line)", overflow: "hidden" }}>
      {/* Header */}
      <div style={{ padding: "14px 22px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--line)", background: "var(--bg-2)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <span style={{ width: 8, height: 8, background: accent, boxShadow: `0 0 8px ${accent}`, animation: "pulse-dot 1.4s infinite" }} />
          <span className="eyebrow" style={{ fontSize: 10, color: accent }}>边缘节点-001 · 实时</span>
          <span className="mono" style={{ fontSize: 11, color: "var(--fg-2)" }}>Orange Pi 5 Plus · RK3588 16GB · 6 TOPS NPU · 8 ARM 核</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
          <div style={{ display: "inline-flex", border: "1px solid var(--line)", background: "var(--bg-1)" }}>
            {modeOpts.map(o => (
              <button key={o.v} onClick={() => onModeChange?.(o.v)} style={{
                padding: "5px 12px", fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.12em",
                fontWeight: 600, textTransform: "uppercase",
                background: mode === o.v ? accent : "transparent",
                color: mode === o.v ? "var(--bg)" : "var(--fg-2)",
                border: "none", borderRight: o.v !== "trace" ? "1px solid var(--line)" : "none",
                cursor: "pointer",
              }}>{o.l}</button>
            ))}
          </div>
          <span style={{ width: 1, height: 20, background: "var(--line)" }} />
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2 }}>
            <span className="eyebrow" style={{ fontSize: 9 }}>LPDDR4</span>
            <span className="mono" style={{ fontSize: 12, color: "var(--fg-1)", fontWeight: 500 }}>{ramUsed.toFixed(1)}/16 GB</span>
          </div>
        </div>
      </div>

      {/* SVG chip stage */}
      <div style={{ position: "relative", padding: "8px 0" }}>
        <div style={{ position: "absolute", inset: 0, pointerEvents: "none", backgroundImage: "linear-gradient(rgba(255,255,255,0.018) 1px, transparent 1px),linear-gradient(90deg, rgba(255,255,255,0.018) 1px, transparent 1px)", backgroundSize: "40px 40px" }} />
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" style={{ width: "100%", display: "block", height: "auto" }}>
          <defs>
            <linearGradient id="chip-fill-v4" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#15151c" /><stop offset="100%" stopColor="#0a0a10" /></linearGradient>
            <linearGradient id="cg0" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stopColor="var(--core-0)" stopOpacity="0.42" /><stop offset="100%" stopColor="var(--core-0)" stopOpacity="0.06" /></linearGradient>
            <linearGradient id="cg1" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stopColor="var(--core-1)" stopOpacity="0.42" /><stop offset="100%" stopColor="var(--core-1)" stopOpacity="0.06" /></linearGradient>
            <linearGradient id="cg2" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stopColor="var(--core-2)" stopOpacity="0.42" /><stop offset="100%" stopColor="var(--core-2)" stopOpacity="0.06" /></linearGradient>
          </defs>

          {/* Camera */}
          <rect x={30} y={camY} width={140} height={130} fill="var(--bg-2)" stroke="var(--line)" />
          <text x={100} y={camY + 23} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">输入</text>
          <circle cx={100} cy={camY + 60} r={26} fill="none" stroke={captureActive ? accent : "var(--fg-3)"} strokeWidth="1.5" style={captureActive ? { filter: `drop-shadow(0 0 6px ${accent})` } : {}} />
          <circle cx={100} cy={camY + 60} r={14} fill="none" stroke={captureActive ? accent : "var(--fg-3)"} strokeWidth="1" />
          <circle cx={100} cy={camY + 60} r={4} fill={captureActive ? accent : "var(--fg-3)"} />
          {captureActive && <circle cx={100} cy={camY + 60} r={26} fill="none" stroke={accent} strokeWidth="1" style={{ transformOrigin: `100px ${camY + 60}px`, animation: "ring-expand 1.2s ease-out infinite" }} />}
          <text x={100} y={camY + 112} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="10" fill="var(--fg-1)">V4L2 · MJPEG</text>
          <text x={100} y={camY + 125} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)">1280×1024 · 30 fps</text>

          {/* Trace line left */}
          <line x1={170} y1={camY + 65} x2={235} y2={camY + 65} stroke="var(--line-hot)" strokeWidth="1.5" strokeDasharray="3 4" />
          {captureActive && <line x1={170} y1={camY + 65} x2={235} y2={camY + 65} stroke={accent} strokeWidth="1.5" style={{ filter: `drop-shadow(0 0 4px ${accent})` }} />}
          {showTraces && mode === "trace" && captureActive && [0, 1, 2].map(i => (
            <circle key={i} r="3" fill={accent} style={{ offsetPath: `path("M 170 ${camY + 65} L 235 ${camY + 65}")`, offsetDistance: "0%", animation: `packet-flow 0.8s linear ${i * 0.22}s infinite`, filter: `drop-shadow(0 0 4px ${accent})` }} />
          ))}

          {/* Chip package */}
          <rect x={235} y={chipY} width={830} height={chipH} fill="url(#chip-fill-v4)" stroke="var(--line-hot)" strokeWidth="1" rx={3} />
          <rect x={250} y={innerY} width={800} height={innerH} fill="none" stroke="var(--line-soft)" strokeDasharray="3 3" rx={2} />

          {/* Package pins (xray/trace only) */}
          {dense && Array.from({ length: 30 }, (_, i) => {
            const px = 260 + i * 26;
            return (
              <g key={i}>
                <line x1={px} y1={chipY - 4} x2={px} y2={chipY} stroke="var(--fg-4)" strokeWidth="1.5" />
                <line x1={px} y1={chipY + chipH} x2={px} y2={chipY + chipH + 4} stroke="var(--fg-4)" strokeWidth="1.5" />
              </g>
            );
          })}

          <text x={650} y={mode === "product" ? 105 : 100} textAnchor="middle" fontFamily="var(--font-sans)" fontSize="13" fontWeight="600" fill="var(--fg-1)" letterSpacing="0.20em">ROCKCHIP RK3588</text>
          <text x={650} y={mode === "product" ? 121 : 116} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">SoC · 8nm · 8 核 CPU · 3 核 NPU · Mali-G610 · 6 TOPS · 16GB LPDDR4</text>

          {/* NPU label */}
          <text x={250} y={npuY - 12} fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">── NPU 集群 ──────────────────────────────────────────</text>

          {/* NPU cores */}
          {[
            { x: 278, title: "NPU.0", model: "EfficientAD-S", task: "异常检测", load: npuLoads[0], ms: STAGE_REAL_MS.core0, color: "var(--core-0)", gradId: "cg0", active: c0Active, detail: "PDN · 256×256 · INT8", thru: "≈ 208 fps" },
            { x: 528, title: "NPU.1", model: "FastSAM-s", task: "分割掩码", load: npuLoads[1], ms: STAGE_REAL_MS.core1, color: "var(--core-1)", gradId: "cg1", active: c1Active, detail: "YOLOv8-seg · 640×640 · INT8", thru: "≈ 20 fps" },
            { x: 778, title: "NPU.2", model: "Qwen3-VL", task: "VLM 描述", load: npuLoads[2], ms: STAGE_REAL_MS.core2, color: "var(--core-2)", gradId: "cg2", active: c2Active, detail: "W8A8 · ctx 4096 · RKLLM", thru: "≈ 0.43 fps" },
          ].map(npu => {
            const ny = npuY, nh = 170;
            return (
              <g key={npu.x}>
                <rect x={npu.x} y={ny} width={240} height={nh} fill="var(--bg-2)" stroke={npu.active ? npu.color : "var(--line)"} strokeWidth={npu.active ? 1.5 : 1} />
                {npu.active && <rect x={npu.x} y={ny} width={240} height={nh} fill={`url(#${npu.gradId})`} />}
                {[[npu.x, ny, npu.x + 8, ny, npu.x, ny + 8], [npu.x + 240, ny, npu.x + 232, ny, npu.x + 240, ny + 8], [npu.x, ny + nh, npu.x + 8, ny + nh, npu.x, ny + nh - 8], [npu.x + 240, ny + nh, npu.x + 232, ny + nh, npu.x + 240, ny + nh - 8]].map((p, i) => (
                  <polyline key={i} points={`${p[2]},${p[3]} ${p[0]},${p[1]} ${p[4]},${p[5]}`} fill="none" stroke={npu.active ? npu.color : "var(--fg-4)"} strokeWidth="1" />
                ))}
                <rect x={npu.x} y={ny} width={240} height={20} fill={npu.active ? `color-mix(in srgb, ${npu.color} 22%, transparent)` : "var(--bg-3)"} />
                <text x={npu.x + 10} y={ny + 14} fontFamily="var(--font-mono)" fontSize="9" fill={npu.active ? npu.color : "var(--fg-3)"} letterSpacing="0.12em">{npu.title}</text>
                {npu.active && <circle cx={npu.x + 228} cy={ny + 10} r={3} fill={npu.color} style={{ animation: "pulse-dot 0.8s infinite" }} />}
                {npu.title === "NPU.2" && !npu.active && <text x={npu.x + 230} y={ny + 14} textAnchor="end" fontFamily="var(--font-mono)" fontSize="8" fill="var(--core-2)" letterSpacing="0.1em">瓶颈</text>}
                <text x={npu.x + 120} y={ny + 44} textAnchor="middle" fontFamily="var(--font-sans)" fontSize="16" fontWeight="600" fill={npu.active ? "var(--fg)" : "var(--fg-1)"}>{npu.model}</text>
                <text x={npu.x + 120} y={ny + 60} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.1em">{npu.task}</text>
                <text x={npu.x + 120} y={ny + 100} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="30" fontWeight="500" fill={npu.color} style={npu.active ? { filter: `drop-shadow(0 0 8px ${npu.color})` } : {}}>
                  {npu.ms < 100 ? npu.ms.toFixed(1) : Math.round(npu.ms)}<tspan fontSize="13" fill="var(--fg-3)" dx="2">ms p50</tspan>
                </text>
                {dense && (
                  <g transform={`translate(${npu.x + 14}, ${ny + 122})`}>
                    <text x={0} y={0} fontFamily="var(--font-mono)" fontSize="8" fill="var(--fg-3)" letterSpacing="0.1em">负载</text>
                    <text x={212} y={0} textAnchor="end" fontFamily="var(--font-mono)" fontSize="10" fill={npu.color} fontWeight="600">{Math.round(npu.load)}%</text>
                    <rect x={0} y={6} width={212} height={4} fill="var(--bg-4)" />
                    <rect x={0} y={6} width={212 * (npu.load / 100)} height={4} fill={npu.color} style={npu.active ? { filter: `drop-shadow(0 0 4px ${npu.color})` } : {}} />
                  </g>
                )}
                {dense && (
                  <>
                    <text x={npu.x + 14} y={ny + nh - 14} fontFamily="var(--font-mono)" fontSize="8" fill="var(--fg-3)">{npu.detail}</text>
                    <text x={npu.x + 226} y={ny + nh - 14} textAnchor="end" fontFamily="var(--font-mono)" fontSize="8" fill="var(--fg-2)">{npu.thru}</text>
                  </>
                )}
                {!dense && <text x={npu.x + 120} y={ny + nh - 16} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.08em">{npu.detail}</text>}
              </g>
            );
          })}

          {/* ARM cores (xray/trace only) */}
          {dense && (
            <>
              <text x={250} y={340} fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">── ARM 集群 ──────────────────────────────────────────</text>
              {[0, 1, 2, 3].map(i => {
                const cx = 278 + i * 92, cy = 350, cw = 84, ch = 68;
                const load = cpuLoads[i], isHot = load > 60;
                return (
                  <g key={`a76_${i}`}>
                    <rect x={cx} y={cy} width={cw} height={ch} fill={isHot ? `color-mix(in srgb, var(--core-0) 18%, var(--bg-3))` : "var(--bg-3)"} stroke={isHot ? "var(--core-0)" : "var(--line)"} strokeWidth={isHot ? 1 : 0.8} />
                    <circle cx={cx + 4} cy={cy + 4} r={1.5} fill="var(--core-0)" opacity={0.8} />
                    <text x={cx + cw / 2} y={cy + 14} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-1)" fontWeight="600">A76·{i}</text>
                    <text x={cx + cw / 2} y={cy + 25} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="7" fill="var(--fg-3)">2.4GHz</text>
                    <text x={cx + cw / 2} y={cy + 45} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="15" fontWeight="500" fill={isHot ? "var(--core-0)" : "var(--fg-2)"} style={isHot ? { filter: "drop-shadow(0 0 4px var(--core-0))" } : {}}>
                      {Math.round(load)}<tspan fontSize="8" fill="var(--fg-3)" dx="0.5">%</tspan>
                    </text>
                    <rect x={cx + 6} y={cy + ch - 8} width={cw - 12} height={2} fill="var(--bg-4)" />
                    <rect x={cx + 6} y={cy + ch - 8} width={(cw - 12) * (load / 100)} height={2} fill="var(--core-0)" />
                  </g>
                );
              })}
              <line x1={655} y1={350} x2={655} y2={418} stroke="var(--line-soft)" strokeDasharray="2 3" />
              {[0, 1, 2, 3].map(i => {
                const cx = 660 + i * 76, cy = 350, cw = 68, ch = 68;
                const load = cpuLoads[4 + i], isHot = load > 60;
                return (
                  <g key={`a55_${i}`}>
                    <rect x={cx} y={cy} width={cw} height={ch} fill={isHot ? `color-mix(in srgb, var(--fg-2) 18%, var(--bg-3))` : "var(--bg-3)"} stroke={isHot ? "var(--fg-2)" : "var(--line)"} strokeWidth={isHot ? 1 : 0.8} />
                    <circle cx={cx + 4} cy={cy + 4} r={1.5} fill="var(--fg-3)" opacity={0.8} />
                    <text x={cx + cw / 2} y={cy + 14} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-1)" fontWeight="600">A55·{i}</text>
                    <text x={cx + cw / 2} y={cy + 25} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="7" fill="var(--fg-3)">1.8GHz</text>
                    <text x={cx + cw / 2} y={cy + 45} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="14" fontWeight="500" fill={isHot ? "var(--fg-2)" : "var(--fg-3)"}>
                      {Math.round(load)}<tspan fontSize="8" fill="var(--fg-3)" dx="0.5">%</tspan>
                    </text>
                    <rect x={cx + 6} y={cy + ch - 8} width={cw - 12} height={2} fill="var(--bg-4)" />
                    <rect x={cx + 6} y={cy + ch - 8} width={(cw - 12) * (load / 100)} height={2} fill="var(--fg-2)" />
                  </g>
                );
              })}
              {/* Mali GPU */}
              <g>
                <rect x={970} y={350} width={92} height={68} fill="var(--bg-3)" stroke="var(--line)" />
                <text x={1016} y={364} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-1)" fontWeight="600">Mali-G610</text>
                <text x={1016} y={375} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="7" fill="var(--fg-3)">MP4 · OpenCL</text>
                <text x={1016} y={395} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="14" fontWeight="500" fill="var(--fg-3)">空闲</text>
                <text x={1016} y={410} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="7" fill="var(--fg-3)">RGA 优先</text>
              </g>

              {/* LPDDR4 memory bar */}
              <text x={250} y={448} fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">── 共享内存 ──────────────────────────────────────────</text>
              <g>
                <rect x={278} y={458} width={784} height={56} fill="var(--bg-3)" stroke="var(--line)" />
                <text x={290} y={478} fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">LPDDR4X · 16 GB · 64 位 · 4266 MT/s</text>
                <rect x={290} y={488} width={760} height={8} fill="var(--bg-4)" />
                <rect x={290} y={488} width={760 * (ramUsed / 16)} height={8} fill={accent} opacity={0.78} />
                <text x={290 + 760 * (ramUsed / 16) - 4} y={510} textAnchor="end" fontFamily="var(--font-mono)" fontSize="8" fill="var(--fg-2)">
                  VLM 3.1G · 模型 4.8G · 运行时 1.3G
                </text>
                <text x={1050} y={478} textAnchor="end" fontFamily="var(--font-mono)" fontSize="10" fill="var(--fg-1)">{ramUsed.toFixed(1)} / 16.0 GB</text>
              </g>
            </>
          )}

          {/* Trace line right */}
          <line x1={1065} y1={camY + 65} x2={1130} y2={camY + 65} stroke="var(--line-hot)" strokeWidth="1.5" strokeDasharray="3 4" />
          {uploadActive && <line x1={1065} y1={camY + 65} x2={1130} y2={camY + 65} stroke={accent} strokeWidth="1.5" style={{ filter: `drop-shadow(0 0 4px ${accent})` }} />}
          {showTraces && mode === "trace" && uploadActive && [0, 1, 2].map(i => (
            <circle key={i} r="3" fill={accent} style={{ offsetPath: `path("M 1065 ${camY + 65} L 1130 ${camY + 65}")`, offsetDistance: "0%", animation: `packet-flow 0.8s linear ${i * 0.22}s infinite`, filter: `drop-shadow(0 0 4px ${accent})` }} />
          ))}

          {/* Upload */}
          <rect x={1130} y={camY} width={140} height={130} fill="var(--bg-2)" stroke="var(--line)" />
          <text x={1200} y={camY + 23} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">上行</text>
          <g transform={`translate(1175, ${camY + 42})`}>
            <rect x={0} y={0} width={50} height={12} fill="none" stroke={uploadActive ? accent : "var(--fg-3)"} />
            <rect x={0} y={14} width={50} height={12} fill="none" stroke={uploadActive ? accent : "var(--fg-3)"} />
            <rect x={0} y={28} width={50} height={12} fill="none" stroke={uploadActive ? accent : "var(--fg-3)"} />
            <circle cx={6} cy={6} r={1.5} fill={uploadActive ? accent : "var(--fg-3)"} />
            <circle cx={6} cy={20} r={1.5} fill={uploadActive ? accent : "var(--fg-3)"} />
            <circle cx={6} cy={34} r={1.5} fill={uploadActive ? accent : "var(--fg-3)"} style={uploadActive ? { animation: "pulse-dot 0.6s infinite" } : {}} />
          </g>
          <text x={1200} y={camY + 108} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="10" fill="var(--fg-1)">FastAPI · POST</text>
          <text x={1200} y={camY + 121} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)">/api/edge/report</text>
        </svg>
      </div>

      {/* Frame journey rail */}
      <div style={{ borderTop: "1px solid var(--line)", padding: "16px 22px", display: "grid", gridTemplateColumns: `repeat(${journey.length}, 1fr) auto`, gap: 0, alignItems: "stretch", background: "var(--bg-2)" }}>
        {journey.map((n, i) => {
          const active = phase.stage === n.stage;
          return (
            <div key={n.stage} style={{ display: "flex", flexDirection: "column", gap: 4, paddingRight: 14, position: "relative" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 8, height: 8, background: active ? n.color : "var(--fg-4)", boxShadow: active ? `0 0 6px ${n.color}` : "none" }} />
                <span className="mono" style={{ fontSize: 10, color: active ? n.color : "var(--fg-2)", letterSpacing: "0.12em", fontWeight: 600, textTransform: "uppercase" }}>{n.label}</span>
              </div>
              <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", paddingLeft: 16 }}>→ {n.out}</span>
              {i < journey.length - 1 && <span style={{ position: "absolute", right: 0, top: 6, height: 1, width: 14, background: "var(--line-hot)" }} />}
            </div>
          );
        })}
        <div style={{ display: "flex", alignItems: "center", gap: 10, paddingLeft: 18, borderLeft: "1px solid var(--line)" }}>
          <span className="eyebrow">当前帧</span>
          <span className="mono" style={{ fontSize: 12, color: "var(--fg)" }}>{phase.frameId ?? "—"}</span>
        </div>
      </div>
    </div>
  );
}
