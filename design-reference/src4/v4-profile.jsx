// V4 Profile page — Chrome-trace style timeline with filmstrip + bottleneck summary above.

const { useState: _prS, useEffect: _prE, useMemo: _prM, useRef: _prR } = React;

const LANE_GROUPS = [
  {
    label: "SOFTWARE THREADS",
    tids: ["T1.capture", "T2.pipeline", "T3.vlm", "T4.upload"],
    labels: {
      "T1.capture":  { name: "T1 · capture",  hint: "V4L2 dequeue" },
      "T2.pipeline": { name: "T2 · pipeline", hint: "RGA + EAD + FastSAM" },
      "T3.vlm":      { name: "T3 · vlm",      hint: "Qwen3-VL prompt + decode" },
      "T4.upload":   { name: "T4 · upload",   hint: "libcurl POST" },
    },
  },
  {
    label: "NPU HARDWARE",
    tids: ["NPU.core0", "NPU.core1", "NPU.core2"],
    labels: {
      "NPU.core0": { name: "NPU.0", hint: "EfficientAD-S [INT8]" },
      "NPU.core1": { name: "NPU.1", hint: "FastSAM-s [INT8]" },
      "NPU.core2": { name: "NPU.2", hint: "Qwen3-VL [W8A8]" },
    },
  },
  {
    label: "ARM CORES",
    tids: ["CPU.A76_0", "CPU.A76_1", "CPU.A76_2", "CPU.A76_3",
           "CPU.A55_0", "CPU.A55_1", "CPU.A55_2", "CPU.A55_3"],
    labels: {
      "CPU.A76_0": { name: "A76.0", hint: "2.4 GHz · perf"  },
      "CPU.A76_1": { name: "A76.1", hint: "2.4 GHz · perf"  },
      "CPU.A76_2": { name: "A76.2", hint: "2.4 GHz · perf"  },
      "CPU.A76_3": { name: "A76.3", hint: "2.4 GHz · perf"  },
      "CPU.A55_0": { name: "A55.0", hint: "1.8 GHz · eff"   },
      "CPU.A55_1": { name: "A55.1", hint: "1.8 GHz · eff"   },
      "CPU.A55_2": { name: "A55.2", hint: "1.8 GHz · eff"   },
      "CPU.A55_3": { name: "A55.3", hint: "1.8 GHz · eff"   },
    },
  },
];

const CAT_COLOR = {
  io:           "#7cdcff",
  mem:          "#7d869c",
  rga:          "#ffbf5c",
  infer:        "var(--acc)",
  npu:          "var(--acc)",
  cpu:          "#b07cff",
  sync:         "#555d72",
  "vlm-prompt": "#ff7a90",
  "vlm-decode": "#ff5c7a",
  "vlm-encode": "#f472b6",
};

function ProfilePage({ defects, accent = "var(--acc)", initialFrameIdx = 0 }){
  const [frameIdx, setFrameIdx] = _prS(initialFrameIdx);
  _prE(() => { setFrameIdx(initialFrameIdx); }, [initialFrameIdx]);

  const [zoom, setZoom] = _prS({ start_us: 0, end_us: 0 });
  const [hover, setHover] = _prS(null);
  const [showCritical, setShowCritical] = _prS(true);

  const defect = defects[frameIdx];

  const span = _prM(() => {
    if (!defect?.trace_events?.length) return { start: 0, end: 1000 };
    let min = Infinity, max = -Infinity;
    for (const e of defect.trace_events){
      if (e.ts < min) min = e.ts;
      if (e.ts + e.dur > max) max = e.ts + e.dur;
    }
    return { start: min, end: max };
  }, [defect]);

  const visible = (zoom.start_us === 0 && zoom.end_us === 0) ? span : { start: zoom.start_us, end: zoom.end_us };
  const totalDur = visible.end - visible.start;

  const byTid = _prM(() => {
    const m = {};
    if (defect?.trace_events) for (const e of defect.trace_events){
      (m[e.tid] = m[e.tid] || []).push(e);
    }
    return m;
  }, [defect]);

  if (!defect) return <EmptyProfile />;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      {/* Filmstrip */}
      <Filmstrip defects={defects.slice(0, 14)} frameIdx={frameIdx} onChange={setFrameIdx} />

      {/* Bottleneck summary cards */}
      <BottleneckSummary defect={defect} byTid={byTid} accent={accent} />

      {/* Header */}
      <ProfileHeader
        defect={defect}
        defectCount={defects.length}
        frameIdx={frameIdx}
        onChangeFrame={setFrameIdx}
        onResetZoom={() => setZoom({ start_us: 0, end_us: 0 })}
        zoomed={zoom.start_us > 0 || zoom.end_us > 0}
        showCritical={showCritical}
        setShowCritical={setShowCritical}
        accent={accent} />

      {/* Trace + right-side explanation */}
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 320px", gap: 14 }}>
        <TraceViewer
          defect={defect}
          byTid={byTid}
          visible={visible}
          totalDur={totalDur}
          onZoom={(s, e) => setZoom({ start_us: s, end_us: e })}
          onHover={setHover}
          hover={hover}
          showCritical={showCritical}
          accent={accent} />
        <BottleneckExplanation defect={defect} byTid={byTid} accent={accent} />
      </div>
    </div>
  );
}

// ── Filmstrip ────────────────────────────────────────────────────────────
function Filmstrip({ defects, frameIdx, onChange }){
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
        <span className="eyebrow">帧胶片 · 点击切换</span>
        <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>最近 {defects.length} 帧</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: `repeat(${defects.length}, 1fr)`, gap: 4 }}>
        {defects.map((d, i) => {
          const total = Math.round(d.pipeline_ms.efficientad + d.pipeline_ms.fastsam + d.pipeline_ms.qwen3vl);
          const sevColor = { low: "var(--ok)", medium: "var(--warn)", high: "var(--crit)" }[d.severity];
          const active = i === frameIdx;
          return (
            <button key={d.id} onClick={() => onChange(i)} style={{
              padding: 0, background: "var(--bg-1)",
              border: active ? `2px solid var(--acc)` : "1px solid var(--line)",
              cursor: "pointer", position: "relative", overflow: "hidden",
              boxShadow: active ? "0 0 12px var(--acc-glow)" : "none",
            }}>
              <div style={{ position: "relative", width: "100%", aspectRatio: "16/10", overflow: "hidden" }}>
                <SimulatedSample category={d.category} />
                <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
                  {d.bboxes.slice(0, 1).map((b, j) => (
                    <rect key={j} x={b.x*100} y={b.y*100} width={b.w*100} height={b.h*100}
                          fill="none" stroke={sevColor} strokeWidth="0.4" vectorEffect="non-scaling-stroke" />
                  ))}
                </svg>
                {/* severity edge */}
                <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: sevColor }} />
              </div>
              <div style={{
                display: "flex", justifyContent: "space-between", padding: "3px 6px",
                fontFamily: "var(--font-mono)", fontSize: 8.5, color: "var(--fg-2)",
                borderTop: "1px solid var(--line)",
                background: active ? "var(--bg-2)" : "var(--bg-1)",
              }}>
                <span style={{ color: active ? "var(--fg)" : "var(--fg-3)" }}>#{d.id}</span>
                <span style={{ color: total > 2800 ? "var(--warn)" : "var(--fg-3)" }}>{total}ms</span>
              </div>
              <div style={{
                fontFamily: "var(--font-mono)", fontSize: 8,
                padding: "0 6px 3px", color: variantColor(d.variant),
                background: active ? "var(--bg-2)" : "var(--bg-1)",
                textAlign: "left", letterSpacing: "0.02em",
              }}>{d.variant}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── Bottleneck Summary Cards ─────────────────────────────────────────────
function BottleneckSummary({ defect, byTid, accent }){
  const total_us = defect.trace_events ? Math.max(...defect.trace_events.map(e => e.ts + e.dur)) : 0;
  const npu0 = (byTid["NPU.core0"] || []).reduce((s, e) => s + e.dur, 0);
  const npu1 = (byTid["NPU.core1"] || []).reduce((s, e) => s + e.dur, 0);
  const npu2 = (byTid["NPU.core2"] || []).reduce((s, e) => s + e.dur, 0);
  const npuTotal = npu0 + npu1 + npu2;

  const prompt = defect.trace_events.filter(e => e.cat === "vlm-prompt" && e.tid === "NPU.core2").reduce((s, e) => s + e.dur, 0);
  const decode = defect.trace_events.filter(e => e.cat === "vlm-decode" && e.tid === "NPU.core2").reduce((s, e) => s + e.dur, 0);
  const promptShare = (prompt / Math.max(1, prompt + decode)) * 100;

  const upload = (byTid["T4.upload"] || []).reduce((s, e) => s + e.dur, 0);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 1, background: "var(--line)", border: "1px solid var(--line)" }}>
      <SumCard label="关键路径" value={(npuTotal / 1000).toFixed(1)} unit="ms"
               sub="NPU 串行累积" c={accent} big />
      <SumCard label="NPU.2 占比" value={`${Math.round((npu2 / npuTotal) * 100)}`} unit="%"
               sub={`${(npu2/1000).toFixed(1)} ms / ${(npuTotal/1000).toFixed(1)} ms`} c="var(--core-2)" big />
      <SumCard label="提示 vs 解码" value={`${Math.round(promptShare)}/${Math.round(100-promptShare)}`} unit="%"
               sub={`${(prompt/1000).toFixed(0)} ms prompt · ${(decode/1000).toFixed(0)} ms decode`} c="var(--fg)" />
      <SumCard label="上传开销" value={(upload / 1000).toFixed(0)} unit="ms"
               sub={`${((upload / total_us) * 100).toFixed(1)}% of E2E`} c="var(--fg)" />
    </div>
  );
}

function SumCard({ label, value, unit, sub, c = "var(--fg)", big }){
  return (
    <div style={{ background: "var(--bg-1)", padding: "14px 16px" }}>
      <div className="eyebrow" style={{ fontSize: 9 }}>{label}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginTop: 6 }}>
        <span className="mono" style={{
          fontSize: big ? 28 : 22, fontWeight: 500, color: c,
          letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums",
        }}>{value}</span>
        {unit && <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>{unit}</span>}
      </div>
      <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginTop: 3 }}>{sub}</div>
    </div>
  );
}

// ── Header ───────────────────────────────────────────────────────────────
function ProfileHeader({ defect, defectCount, frameIdx, onChangeFrame, onResetZoom, zoomed, showCritical, setShowCritical, accent }){
  const total = (defect.trace_events ? Math.max(...defect.trace_events.map(e => e.ts + e.dur)) : 0) / 1000;
  return (
    <div style={{
      background: "var(--bg-1)", border: "1px solid var(--line)", padding: "16px 20px",
      display: "flex", justifyContent: "space-between", alignItems: "center", gap: 18, flexWrap: "wrap",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 22, flexWrap: "wrap" }}>
        <div>
          <div className="eyebrow">当前帧</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 4 }}>
            <span className="mono" style={{ fontSize: 22, color: "var(--fg)", fontWeight: 500 }}>#{defect.id}</span>
            <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>
              · {defect.line_id} · {CATEGORY_LABEL[defect.category] || defect.category}
            </span>
          </div>
        </div>
        <span style={{ width: 1, height: 36, background: "var(--line)" }} />
        <div>
          <div className="eyebrow">端到端延迟</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginTop: 4 }}>
            <span className="mono" style={{ fontSize: 22, color: accent, fontWeight: 500, textShadow: `0 0 12px color-mix(in srgb, ${accent} 30%, transparent)` }}>
              {total.toFixed(1)}
            </span>
            <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>ms</span>
          </div>
        </div>
        <span style={{ width: 1, height: 36, background: "var(--line)" }} />
        <div>
          <div className="eyebrow">VARIANT</div>
          <div style={{ marginTop: 4 }}>
            <VariantPill value={defect.variant} />
          </div>
        </div>
        <span style={{ width: 1, height: 36, background: "var(--line)" }} />
        <div>
          <div className="eyebrow">事件数</div>
          <span className="mono" style={{ fontSize: 16, color: "var(--fg-1)", marginTop: 4, display: "inline-block" }}>
            {defect.trace_events?.length ?? 0}
          </span>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <ToolBtn onClick={() => onChangeFrame(Math.min(defectCount - 1, frameIdx + 1))} disabled={frameIdx >= defectCount - 1}>‹ 更早</ToolBtn>
        <span className="mono" style={{ fontSize: 11, color: "var(--fg-2)", padding: "0 4px" }}>
          {frameIdx + 1} / {defectCount}
        </span>
        <ToolBtn onClick={() => onChangeFrame(Math.max(0, frameIdx - 1))} disabled={frameIdx === 0}>更新 ›</ToolBtn>
        <span style={{ width: 1, height: 20, background: "var(--line)", margin: "0 6px" }} />
        <ToolBtn onClick={() => setShowCritical(!showCritical)} active={showCritical}>关键路径</ToolBtn>
        <ToolBtn onClick={onResetZoom} disabled={!zoomed}>重置缩放</ToolBtn>
        <ToolBtn onClick={() => copyTraceJson(defect)}>复制追踪</ToolBtn>
        <ToolBtn onClick={() => downloadTrace(defect)}>↓ 导出</ToolBtn>
      </div>
    </div>
  );
}

function copyTraceJson(defect){
  try {
    navigator.clipboard.writeText(JSON.stringify({ traceEvents: defect.trace_events, frameId: defect.id }, null, 2));
  } catch {}
}
function downloadTrace(defect){
  const blob = new Blob([JSON.stringify({ traceEvents: defect.trace_events, frameId: defect.id }, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = `trace_${defect.id}.json`;
  a.click(); URL.revokeObjectURL(url);
}

function ToolBtn({ children, onClick, disabled, active }){
  return (
    <button onClick={onClick} disabled={disabled} style={{
      background: active ? "var(--bg-3)" : "transparent",
      color: disabled ? "var(--fg-4)" : active ? "var(--fg)" : "var(--fg-2)",
      border: `1px solid ${active ? "var(--fg-2)" : "var(--line)"}`,
      padding: "4px 10px", fontSize: 11, fontFamily: "var(--font-mono)",
      cursor: disabled ? "default" : "pointer",
      letterSpacing: "0.04em",
    }}>{children}</button>
  );
}

// ── Trace Viewer ─────────────────────────────────────────────────────────
function TraceViewer({ defect, byTid, visible, totalDur, onZoom, onHover, hover, showCritical, accent }){
  const ref = _prR(null);
  const [w, setW] = _prS(1100);
  _prE(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(es => { for (const e of es) setW(e.contentRect.width); });
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);

  const LANE_H = 24, LANE_GAP = 2, GROUP_GAP = 18, GROUP_HEADER_H = 22;
  const labelW = 110, padR = 12, padT = 36;
  const innerW = Math.max(200, w - labelW - padR);

  const lanes = [];
  let y = padT;
  for (const group of LANE_GROUPS){
    lanes.push({ kind: "group", label: group.label, y });
    y += GROUP_HEADER_H;
    for (const tid of group.tids){
      lanes.push({ kind: "lane", tid, y, ...(group.labels[tid] || {}) });
      y += LANE_H + LANE_GAP;
    }
    y += GROUP_GAP;
  }
  const totalH = y + 6;

  const us2x = us => labelW + ((us - visible.start) / totalDur) * innerW;

  const ticks = _prM(() => {
    const ms = totalDur / 1000;
    let step_ms = 100;
    if (ms > 4000) step_ms = 500;
    else if (ms > 2000) step_ms = 250;
    else if (ms > 1000) step_ms = 200;
    else if (ms > 500)  step_ms = 100;
    else if (ms > 200)  step_ms = 50;
    else if (ms > 100)  step_ms = 25;
    else                step_ms = 10;
    const step_us = step_ms * 1000;
    const start_ms = Math.floor(visible.start / step_us) * step_ms;
    const out = [];
    for (let t_ms = start_ms; t_ms * 1000 <= visible.end; t_ms += step_ms) out.push(t_ms);
    return out;
  }, [visible, totalDur]);

  const [dragStart, setDragStart] = _prS(null);
  const [dragEnd, setDragEnd] = _prS(null);
  const onMouseDown = e => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    if (x < labelW) return;
    setDragStart(x); setDragEnd(x);
  };
  const onMouseMove = e => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    if (dragStart != null) setDragEnd(x);
  };
  const onMouseUp = e => {
    if (dragStart == null) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const sX = Math.min(dragStart, x), eX = Math.max(dragStart, x);
    setDragStart(null); setDragEnd(null);
    if (eX - sX > 5){
      const start_us = visible.start + ((sX - labelW) / innerW) * totalDur;
      const end_us   = visible.start + ((eX - labelW) / innerW) * totalDur;
      onZoom(Math.max(0, start_us), end_us);
    }
  };

  return (
    <div ref={ref} style={{
      position: "relative", background: "var(--bg-1)", border: "1px solid var(--line)", overflow: "hidden",
    }}>
      <div style={{
        padding: "10px 14px", borderBottom: "1px solid var(--line)",
        background: "var(--bg-2)",
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <span className="eyebrow">Chrome 追踪 · 横向拖拽可缩放</span>
        <Legend />
      </div>

      <svg width={w} height={totalH}
           onMouseDown={onMouseDown} onMouseMove={onMouseMove} onMouseUp={onMouseUp}
           onMouseLeave={() => { setDragStart(null); setDragEnd(null); onHover(null); }}
           style={{ display: "block", cursor: dragStart != null ? "ew-resize" : "default" }}>
        <g>
          {ticks.map((t_ms, i) => {
            const x = us2x(t_ms * 1000);
            return (
              <g key={i}>
                <line x1={x} y1={padT - 14} x2={x} y2={totalH - 6}
                      stroke="var(--line-soft)" strokeDasharray={t_ms === 0 ? "0" : "1 3"} />
                <text x={x} y={padT - 18} textAnchor="middle"
                      fill="var(--fg-3)" style={{ fontFamily: "var(--font-mono)", fontSize: 9 }}>
                  {t_ms}ms
                </text>
              </g>
            );
          })}
        </g>

        {lanes.map((ln, i) => {
          if (ln.kind === "group"){
            return (
              <g key={i}>
                <text x={6} y={ln.y + 12}
                      fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">
                  {ln.label}
                </text>
                <line x1={labelW} y1={ln.y + 14} x2={w - padR} y2={ln.y + 14}
                      stroke="var(--line-soft)" strokeDasharray="2 4" />
              </g>
            );
          }
          return (
            <g key={i}>
              <rect x={0} y={ln.y} width={labelW - 2} height={LANE_H} fill="var(--bg-2)" />
              <text x={10} y={ln.y + 12}
                    fontFamily="var(--font-mono)" fontSize="10" fill="var(--fg-1)" fontWeight="500">
                {ln.name || ln.tid}
              </text>
              <text x={10} y={ln.y + 22}
                    fontFamily="var(--font-mono)" fontSize="8" fill="var(--fg-3)">
                {ln.hint || ""}
              </text>
              <rect x={labelW} y={ln.y} width={innerW} height={LANE_H}
                    fill={i % 2 === 0 ? "rgba(255,255,255,0.012)" : "transparent"} />
              {(byTid[ln.tid] || []).map((ev, j) => {
                const x = us2x(ev.ts);
                const wBar = Math.max(1.5, ((ev.dur) / totalDur) * innerW);
                if (x + wBar < labelW || x > w - padR) return null;
                const isCritical = showCritical && ln.tid.startsWith("NPU.");
                const color = CAT_COLOR[ev.cat] || "#888";
                return (
                  <g key={j}>
                    <rect x={x} y={ln.y + 4} width={wBar} height={LANE_H - 8}
                          fill={color}
                          opacity={showCritical && !isCritical ? 0.38 : 0.92}
                          style={isCritical ? { filter: `drop-shadow(0 0 3px ${color})` } : {}}
                          onMouseEnter={e => {
                            const r = e.currentTarget.ownerSVGElement.getBoundingClientRect();
                            const ce = e.currentTarget.getBoundingClientRect();
                            onHover({
                              x: ce.left - r.left + ce.width / 2,
                              y: ce.top - r.top,
                              event: ev,
                              laneName: ln.name,
                            });
                          }}
                          onMouseLeave={() => onHover(null)} />
                    {wBar > 60 && (
                      <text x={x + 4} y={ln.y + LANE_H / 2 + 3}
                            fontFamily="var(--font-mono)" fontSize="9"
                            fill="var(--bg)" pointerEvents="none" style={{ fontWeight: 600 }}>
                        {ev.name.length > Math.floor(wBar / 6.5) ? ev.name.slice(0, Math.floor(wBar / 6.5)) + "…" : ev.name}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>
          );
        })}

        {dragStart != null && dragEnd != null && Math.abs(dragEnd - dragStart) > 2 && (
          <rect x={Math.min(dragStart, dragEnd)} y={padT - 14}
                width={Math.abs(dragEnd - dragStart)} height={totalH - padT - 4}
                fill={accent} opacity={0.12}
                stroke={accent} strokeOpacity={0.6} strokeDasharray="2 2" />
        )}
      </svg>

      {hover && <HoverTip hover={hover} />}
    </div>
  );
}

function HoverTip({ hover }){
  const ev = hover.event;
  return (
    <div style={{
      position: "absolute", left: hover.x, top: hover.y,
      transform: "translate(-50%, calc(-100% - 10px))",
      background: "var(--bg)", border: "1px solid var(--fg-2)", padding: "8px 10px",
      pointerEvents: "none", fontSize: 11, lineHeight: 1.5,
      minWidth: 180, maxWidth: 280, boxShadow: "0 4px 16px rgba(0,0,0,0.5)", zIndex: 5,
    }}>
      <div className="mono" style={{ color: "var(--fg)", fontWeight: 600, fontSize: 12 }}>{ev.name}</div>
      <div className="mono" style={{ color: "var(--fg-3)", fontSize: 9, marginTop: 2 }}>{hover.laneName}</div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, gap: 12 }}>
        <span style={{ color: "var(--fg-3)" }}>ts</span>
        <span className="mono" style={{ color: "var(--fg-1)" }}>{(ev.ts / 1000).toFixed(2)}<span style={{ color: "var(--fg-3)" }}>ms</span></span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 2 }}>
        <span style={{ color: "var(--fg-3)" }}>dur</span>
        <span className="mono" style={{ color: CAT_COLOR[ev.cat] || "var(--fg-1)", fontWeight: 600 }}>
          {(ev.dur / 1000).toFixed(2)}<span style={{ color: "var(--fg-3)" }}>ms</span>
        </span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 2 }}>
        <span style={{ color: "var(--fg-3)" }}>cat</span>
        <span className="mono" style={{ color: "var(--fg-1)" }}>{ev.cat}</span>
      </div>
    </div>
  );
}

function Legend(){
  const items = [
    ["NPU 推理", "infer"], ["VLM 提示", "vlm-prompt"], ["VLM 解码", "vlm-decode"],
    ["CPU", "cpu"], ["IO", "io"], ["RGA", "rga"], ["同步", "sync"],
  ];
  return (
    <div style={{ display: "flex", gap: 10 }}>
      {items.map(([l, k]) => (
        <span key={k} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 9, height: 9, background: CAT_COLOR[k] }} />
          <span className="mono" style={{ fontSize: 9, color: "var(--fg-2)" }}>{l}</span>
        </span>
      ))}
    </div>
  );
}

// ── Right-side Bottleneck Explanation ────────────────────────────────────
function BottleneckExplanation({ defect, byTid, accent }){
  const npu0 = (byTid["NPU.core0"] || []).reduce((s, e) => s + e.dur, 0);
  const npu1 = (byTid["NPU.core1"] || []).reduce((s, e) => s + e.dur, 0);
  const npu2 = (byTid["NPU.core2"] || []).reduce((s, e) => s + e.dur, 0);
  const npuTotal = npu0 + npu1 + npu2;
  const npu2Share = npu2 / npuTotal;

  const prompt = defect.trace_events.filter(e => e.cat === "vlm-prompt" && e.tid === "NPU.core2").reduce((s, e) => s + e.dur, 0);
  const decode = defect.trace_events.filter(e => e.cat === "vlm-decode" && e.tid === "NPU.core2").reduce((s, e) => s + e.dur, 0);
  const promptShare = prompt / Math.max(1, prompt + decode);

  // recommendations
  const recs = [];
  if (npu2Share > 0.9) recs.push({ icon: "▸", text: "NPU.2 完全串行——Qwen3-VL 主导关键路径。" });
  if (promptShare > 0.5 && variantIsLora(defect.variant) === false){
    recs.push({ icon: "▸", text: "提示词主导解码——切换至 *_lora 变体可将提示词缩短 14 倍。" });
  } else if (promptShare > 0.5){
    recs.push({ icon: "▸", text: "提示词仍占 VLM 的约一半，建议检查分词器 / 对话模板开销。" });
  } else {
    recs.push({ icon: "▸", text: "解码主导——调节 output_tokens 比缩短提示词更有效。" });
  }
  recs.push({ icon: "▸", text: "EfficientAD-S + FastSAM-s 合计不足 E2E 的 5%，无需优化。" });

  return (
    <div style={{
      background: "var(--bg-1)", border: "1px solid var(--line)",
      padding: 18, display: "flex", flexDirection: "column", gap: 14,
      borderTop: `2px solid ${accent}`,
    }}>
      <div>
        <div className="eyebrow" style={{ color: accent }}>为什么这帧慢</div>
        <h3 style={{ margin: "6px 0 0", fontSize: 16, fontWeight: 600, lineHeight: 1.4 }}>
          Qwen3-VL 在 NPU.2 上占据关键路径的 <span style={{ color: "var(--core-2)" }}>{Math.round(npu2Share * 100)}%</span>。
        </h3>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {recs.map((r, i) => (
          <div key={i} style={{
            padding: "8px 10px", background: "var(--bg-2)",
            border: "1px solid var(--line-soft)", borderLeft: `2px solid ${accent}`,
            fontSize: 12, color: "var(--fg-1)", lineHeight: 1.5,
          }}>
            <span style={{ color: accent, marginRight: 6 }}>{r.icon}</span>{r.text}
          </div>
        ))}
      </div>

      {/* Quick export panel */}
      <div style={{
        marginTop: 4, padding: "10px 12px", background: "var(--bg-2)",
        border: "1px solid var(--line-soft)",
      }}>
        <div className="eyebrow" style={{ marginBottom: 6 }}>导出</div>
        <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", lineHeight: 1.6 }}>
          → 复制追踪 JSON 到剪贴板<br />
          → Download <span style={{ color: "var(--fg-1)" }}>trace_{defect.id}.json</span><br />
          → 拖入 <span style={{ color: "var(--fg-1)" }}>chrome://tracing</span> 或 <span style={{ color: "var(--fg-1)" }}>perfetto.dev</span>
        </div>
      </div>
    </div>
  );
}

function EmptyProfile(){
  return (
    <div style={{
      background: "var(--bg-1)", border: "1px solid var(--line)", padding: 60,
      textAlign: "center", color: "var(--fg-3)",
    }}>
      <span className="mono" style={{ fontSize: 14 }}>暂无追踪事件。</span>
    </div>
  );
}

Object.assign(window, { ProfilePage });
