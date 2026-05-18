// V3 Profile page — Chrome-trace style per-frame timeline.
// Renders defect.trace_events[] as multi-lane gantt with zoom, hover, critical path.

const { useState: _prS, useEffect: _prE, useMemo: _prM, useRef: _prR, useCallback: _prC } = React;

// Lane order — defines vertical position of each track
const LANE_GROUPS = [
  {
    label: "SOFTWARE THREADS",
    tids: ["T1.capture", "T2.pipeline", "T3.vlm", "T4.upload"],
    labels: {
      "T1.capture":  { name: "T1 · capture",  hint: "V4L2 dequeue" },
      "T2.pipeline": { name: "T2 · pipeline", hint: "RGA + EfficientAD + FastSAM" },
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
  io:           "#6dd5ff",
  mem:          "#7d869c",
  rga:          "#ffbf5c",
  infer:        "#c1ff72",
  npu:          "#c1ff72",
  cpu:          "#b07cff",
  sync:         "#555d72",
  "vlm-prompt": "#ff7a90",
  "vlm-decode": "#ff5c7a",
  "vlm-encode": "#f472b6",
};

function ProfilePage({ defects, accent = "var(--acc)" }){
  const [frameIdx, setFrameIdx] = _prS(0);
  const [zoom, setZoom] = _prS({ start_us: 0, end_us: 0 });  // 0/0 = auto-fit
  const [hover, setHover] = _prS(null);  // { x, y, event } or null
  const [showCritical, setShowCritical] = _prS(true);

  const defect = defects[frameIdx];

  // total span
  const span = _prM(() => {
    if (!defect?.trace_events?.length) return { start: 0, end: 1000 };
    let min = Infinity, max = -Infinity;
    for (const e of defect.trace_events){
      if (e.ts < min) min = e.ts;
      if (e.ts + e.dur > max) max = e.ts + e.dur;
    }
    return { start: min, end: max };
  }, [defect]);

  const visible = (zoom.start_us === 0 && zoom.end_us === 0)
    ? span
    : { start: zoom.start_us, end: zoom.end_us };
  const totalDur = visible.end - visible.start;

  // group events by tid
  const byTid = _prM(() => {
    const m = {};
    if (defect?.trace_events){
      for (const e of defect.trace_events){
        if (!m[e.tid]) m[e.tid] = [];
        m[e.tid].push(e);
      }
    }
    return m;
  }, [defect]);

  // critical path: longest chain (just highlight NPU ops chronologically)
  const criticalEvents = _prM(() => {
    if (!defect?.trace_events) return new Set();
    const ids = new Set();
    const npuEvents = defect.trace_events.filter(e => e.tid.startsWith("NPU.")).sort((a,b) => a.ts - b.ts);
    npuEvents.forEach((e, i) => ids.add(`${e.tid}_${e.ts}_${i}`));
    return ids;
  }, [defect]);

  if (!defect){
    return <EmptyProfile />;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <ProfileHeader
        defect={defect}
        defectCount={defects.length}
        frameIdx={frameIdx}
        onChangeFrame={setFrameIdx}
        onResetZoom={() => setZoom({ start_us: 0, end_us: 0 })}
        zoomed={zoom.start_us > 0 || zoom.end_us > 0}
        showCritical={showCritical}
        setShowCritical={setShowCritical}
        accent={accent}
      />

      <TraceViewer
        defect={defect}
        byTid={byTid}
        visible={visible}
        totalDur={totalDur}
        onZoom={(s, e) => setZoom({ start_us: s, end_us: e })}
        onHover={setHover}
        hover={hover}
        showCritical={showCritical}
        accent={accent}
      />

      <ProfileSummary defect={defect} byTid={byTid} accent={accent} />
    </div>
  );
}

// ── Header ────────────────────────────────────────────────────────────────
function ProfileHeader({ defect, defectCount, frameIdx, onChangeFrame, onResetZoom, zoomed, showCritical, setShowCritical, accent }){
  const total = (defect.trace_events ? Math.max(...defect.trace_events.map(e => e.ts + e.dur)) : 0) / 1000;
  return (
    <div style={{
      background: "var(--bg-1)", border: "1px solid var(--line)",
      padding: "16px 20px",
      display: "flex", justifyContent: "space-between", alignItems: "center", gap: 18,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
        <div>
          <div className="eyebrow">INSPECTING FRAME</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 4 }}>
            <span className="mono" style={{ fontSize: 22, color: "var(--fg)", fontWeight: 500 }}>#{defect.id}</span>
            <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>
              · {defect.line_id} · {defect.category}
            </span>
          </div>
        </div>
        <span style={{ width: 1, height: 36, background: "var(--line)" }} />
        <div>
          <div className="eyebrow">END-TO-END</div>
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
          <span style={{
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            width: 28, height: 28, marginTop: 4,
            border: `1px solid ${defect.variant === "A" ? "var(--ab-a)" : "var(--ab-b)"}`,
            color: defect.variant === "A" ? "var(--ab-a)" : "var(--ab-b)",
            fontFamily: "var(--font-mono)", fontSize: 14, fontWeight: 700,
          }}>{defect.variant}</span>
        </div>
        <span style={{ width: 1, height: 36, background: "var(--line)" }} />
        <div>
          <div className="eyebrow">EVENTS</div>
          <span className="mono" style={{ fontSize: 16, color: "var(--fg-1)", marginTop: 4, display: "inline-block" }}>
            {defect.trace_events?.length ?? 0}
          </span>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <ToolBtn onClick={() => onChangeFrame(Math.min(defectCount - 1, frameIdx + 1))} disabled={frameIdx >= defectCount - 1}>‹ Older</ToolBtn>
        <span className="mono" style={{ fontSize: 11, color: "var(--fg-2)", padding: "0 4px" }}>
          {frameIdx + 1} / {defectCount}
        </span>
        <ToolBtn onClick={() => onChangeFrame(Math.max(0, frameIdx - 1))} disabled={frameIdx === 0}>Newer ›</ToolBtn>
        <span style={{ width: 1, height: 20, background: "var(--line)", margin: "0 6px" }} />
        <ToolBtn onClick={() => setShowCritical(!showCritical)} active={showCritical}>Critical path</ToolBtn>
        <ToolBtn onClick={onResetZoom} disabled={!zoomed}>Reset zoom</ToolBtn>
      </div>
    </div>
  );
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

// ── Trace Viewer ──────────────────────────────────────────────────────────
function TraceViewer({ defect, byTid, visible, totalDur, onZoom, onHover, hover, showCritical, accent }){
  const ref = _prR(null);
  const [w, setW] = _prS(1100);
  _prE(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(es => { for (const e of es) setW(e.contentRect.width); });
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);

  const LANE_H = 26;
  const LANE_GAP = 2;
  const GROUP_GAP = 20;
  const GROUP_HEADER_H = 24;
  const labelW = 110;
  const padR = 12;
  const padT = 36;
  const innerW = Math.max(200, w - labelW - padR);

  // build flat list of lanes with their y positions
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

  // ticks — pick nice intervals based on total duration
  const ticks = _prM(() => {
    const ms = totalDur / 1000;
    let step_ms = 100;
    if (ms > 4000)      step_ms = 500;
    else if (ms > 2000) step_ms = 250;
    else if (ms > 1000) step_ms = 200;
    else if (ms > 500)  step_ms = 100;
    else if (ms > 200)  step_ms = 50;
    else if (ms > 100)  step_ms = 25;
    else                step_ms = 10;
    const step_us = step_ms * 1000;
    const start_ms = Math.floor(visible.start / step_us) * step_ms;
    const out = [];
    for (let t_ms = start_ms; t_ms * 1000 <= visible.end; t_ms += step_ms){
      out.push(t_ms);
    }
    return out;
  }, [visible, totalDur]);

  // drag-to-zoom
  const [dragStart, setDragStart] = _prS(null);
  const [dragEnd, setDragEnd] = _prS(null);
  const onMouseDown = e => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    if (x < labelW) return;
    setDragStart(x);
    setDragEnd(x);
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
    const sX = Math.min(dragStart, x);
    const eX = Math.max(dragStart, x);
    setDragStart(null);
    setDragEnd(null);
    if (eX - sX > 5){
      const start_us = visible.start + ((sX - labelW) / innerW) * totalDur;
      const end_us   = visible.start + ((eX - labelW) / innerW) * totalDur;
      onZoom(Math.max(0, start_us), end_us);
    }
  };

  return (
    <div ref={ref} style={{
      position: "relative",
      background: "var(--bg-1)", border: "1px solid var(--line)",
      overflow: "hidden",
    }}>
      <div style={{
        padding: "10px 14px", borderBottom: "1px solid var(--line)",
        background: "var(--bg-2)",
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="eyebrow">CHROME TRACE · drag horizontally to zoom</span>
        </div>
        <Legend />
      </div>

      <svg width={w} height={totalH}
           onMouseDown={onMouseDown}
           onMouseMove={onMouseMove}
           onMouseUp={onMouseUp}
           onMouseLeave={() => { setDragStart(null); setDragEnd(null); onHover(null); }}
           style={{ display: "block", cursor: dragStart != null ? "ew-resize" : "default" }}>
        {/* time axis */}
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

        {/* group headers + lane labels */}
        {lanes.map((ln, i) => {
          if (ln.kind === "group"){
            return (
              <g key={i}>
                <text x={6} y={ln.y + 12}
                      fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.14em">
                  {ln.label}
                </text>
                <line x1={labelW} y1={ln.y + 16} x2={w - padR} y2={ln.y + 16}
                      stroke="var(--line-soft)" strokeDasharray="2 4" />
              </g>
            );
          }
          // lane row
          return (
            <g key={i}>
              <rect x={0} y={ln.y} width={labelW - 2} height={LANE_H} fill="var(--bg-2)" />
              <text x={10} y={ln.y + 13}
                    fontFamily="var(--font-mono)" fontSize="10" fill="var(--fg-1)" fontWeight="500">
                {ln.name || ln.tid}
              </text>
              <text x={10} y={ln.y + 23}
                    fontFamily="var(--font-mono)" fontSize="8" fill="var(--fg-3)">
                {ln.hint || ""}
              </text>
              {/* lane bg */}
              <rect x={labelW} y={ln.y} width={innerW} height={LANE_H}
                    fill={i % 2 === 0 ? "rgba(255,255,255,0.012)" : "transparent"} />
              {/* events on this lane */}
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
                          opacity={isCritical ? 1 : 0.78}
                          stroke={isCritical ? color : "none"}
                          strokeWidth={isCritical ? 0.5 : 0}
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
                            fill="var(--bg)" pointerEvents="none"
                            style={{ fontWeight: 600 }}>
                        {ev.name.length > Math.floor(wBar / 6.5) ? ev.name.slice(0, Math.floor(wBar / 6.5)) + "…" : ev.name}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>
          );
        })}

        {/* drag selection overlay */}
        {dragStart != null && dragEnd != null && Math.abs(dragEnd - dragStart) > 2 && (
          <rect x={Math.min(dragStart, dragEnd)}
                y={padT - 14}
                width={Math.abs(dragEnd - dragStart)}
                height={totalH - padT - 4}
                fill={accent} opacity={0.12}
                stroke={accent} strokeOpacity={0.6} strokeDasharray="2 2" />
        )}
      </svg>

      {/* hover tooltip */}
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
      background: "var(--bg)", border: "1px solid var(--fg-2)",
      padding: "8px 10px", pointerEvents: "none",
      fontSize: 11, lineHeight: 1.5,
      minWidth: 180, maxWidth: 280,
      boxShadow: "0 4px 16px rgba(0,0,0,0.5)",
      zIndex: 5,
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
    ["NPU infer", "infer"],
    ["VLM prompt", "vlm-prompt"],
    ["VLM decode", "vlm-decode"],
    ["CPU", "cpu"],
    ["IO / network", "io"],
    ["RGA", "rga"],
    ["Sync", "sync"],
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

// ── Summary ─────────────────────────────────────────────────────────────────
function ProfileSummary({ defect, byTid, accent }){
  const total_us = defect.trace_events ? Math.max(...defect.trace_events.map(e => e.ts + e.dur)) : 0;
  // per-lane busy time
  const lanes = ["T1.capture", "T2.pipeline", "T3.vlm", "T4.upload"];
  const stats = lanes.map(tid => {
    const events = byTid[tid] || [];
    const busy = events.reduce((s, e) => s + e.dur, 0);
    return { tid, busy, util: total_us > 0 ? busy / total_us : 0, count: events.length };
  });
  // NPU specifically
  const npu = ["NPU.core0", "NPU.core1", "NPU.core2"].map(tid => {
    const events = byTid[tid] || [];
    const busy = events.reduce((s, e) => s + e.dur, 0);
    return { tid, busy, util: total_us > 0 ? busy / total_us : 0 };
  });

  // critical path = sum of NPU times (sequential)
  const criticalPath = npu.reduce((s, n) => s + n.busy, 0);
  const slack = Math.max(0, total_us - criticalPath);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
      {/* Thread utilization */}
      <div style={{ background: "var(--bg-1)", border: "1px solid var(--line)" }}>
        <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--line)", background: "var(--bg-2)" }}>
          <span className="eyebrow">THREAD UTILIZATION</span>
        </div>
        <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 10 }}>
          {stats.map(s => (
            <UtilRow key={s.tid} tid={s.tid} busy_us={s.busy} util={s.util} count={s.count} color={accent} />
          ))}
        </div>
      </div>

      {/* Critical path */}
      <div style={{ background: "var(--bg-1)", border: "1px solid var(--line)" }}>
        <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--line)", background: "var(--bg-2)" }}>
          <span className="eyebrow">CRITICAL PATH · NPU SERIAL</span>
        </div>
        <div style={{ padding: 14 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 1, background: "var(--line)" }}>
            {npu.map((n, i) => {
              const stageColor = ["var(--core-0)", "var(--core-1)", "var(--core-2)"][i];
              const stageName = ["EfficientAD-S", "FastSAM-s", "Qwen3-VL-2B"][i];
              return (
                <div key={n.tid} style={{ background: "var(--bg-1)", padding: "10px 12px" }}>
                  <div className="eyebrow" style={{ fontSize: 9 }}>{n.tid.replace("NPU.", "NPU ")}</div>
                  <div style={{ fontSize: 11, color: "var(--fg-1)", marginTop: 2 }}>{stageName}</div>
                  <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginTop: 8 }}>
                    <span className="mono" style={{ fontSize: 18, color: stageColor, fontWeight: 500 }}>
                      {(n.busy / 1000).toFixed(1)}
                    </span>
                    <span className="mono" style={{ fontSize: 9, color: "var(--fg-3)" }}>ms</span>
                  </div>
                  <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", marginTop: 2 }}>
                    {(n.util * 100).toFixed(1)}% of window
                  </div>
                </div>
              );
            })}
          </div>

          <div style={{
            marginTop: 14, padding: "10px 12px",
            background: "var(--bg-2)", border: "1px solid var(--line-soft)",
            borderLeft: `3px solid ${accent}`,
            display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16,
          }}>
            <div>
              <div className="eyebrow">CRITICAL PATH TOTAL</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginTop: 4 }}>
                <span className="mono" style={{ fontSize: 20, color: "var(--fg)", fontWeight: 500 }}>
                  {(criticalPath / 1000).toFixed(1)}
                </span>
                <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>ms · NPU-bound</span>
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div className="eyebrow">SLACK</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginTop: 4, justifyContent: "flex-end" }}>
                <span className="mono" style={{ fontSize: 20, color: "var(--fg-2)", fontWeight: 500 }}>
                  {(slack / 1000).toFixed(1)}
                </span>
                <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>ms</span>
              </div>
            </div>
          </div>

          <div className="mono" style={{ marginTop: 12, fontSize: 10, color: "var(--fg-3)", lineHeight: 1.6 }}>
            ↳ Qwen3-VL on NPU.2 owns {((npu[2].busy / criticalPath) * 100).toFixed(0)}% of critical path.<br />
            ↳ Shortening prompt or further W8A8 quantization yields the highest ROI.
          </div>
        </div>
      </div>
    </div>
  );
}

function UtilRow({ tid, busy_us, util, count, color }){
  const ms = busy_us / 1000;
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
        <span className="mono" style={{ fontSize: 11, color: "var(--fg-1)", fontWeight: 500 }}>{tid}</span>
        <span style={{ display: "flex", gap: 10, alignItems: "baseline" }}>
          <span className="mono" style={{ fontSize: 9, color: "var(--fg-3)" }}>{count} evt</span>
          <span className="mono" style={{ fontSize: 12, color: "var(--fg)", fontWeight: 500 }}>
            {ms < 100 ? ms.toFixed(2) : Math.round(ms)}<span style={{ color: "var(--fg-3)" }}>ms</span>
          </span>
          <span className="mono" style={{ fontSize: 10, color: "var(--fg-2)", width: 44, textAlign: "right" }}>
            {(util * 100).toFixed(0)}%
          </span>
        </span>
      </div>
      <div style={{ height: 5, background: "var(--bg-3)", border: "1px solid var(--line-soft)" }}>
        <div style={{ width: `${util * 100}%`, height: "100%", background: color, opacity: 0.8 }} />
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
      <span className="mono" style={{ fontSize: 14 }}>No trace events available.</span>
      <div className="mono" style={{ fontSize: 11, marginTop: 8, color: "var(--fg-4)" }}>
        Waiting for first frame to complete…
      </div>
    </div>
  );
}

Object.assign(window, { ProfilePage });
