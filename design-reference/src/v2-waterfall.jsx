// V2 Waterfall — the hero. Shows 3-stage pipeline as a profiler timeline.
// Bottleneck (Qwen3-VL ~2300ms) is visually overwhelming, like Nsight.

const { useState: _wfState, useEffect: _wfEff, useMemo: _wfMemo, useRef: _wfRef } = React;

function PipelineWaterfall({ samples, height = 280 }){
  // samples: array of recent defects [{pipeline_ms: {efficientad, fastsam, qwen3vl}}]
  const ref = _wfRef(null);
  const [w, setW] = _wfState(900);
  _wfEff(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(es => { for (const e of es) setW(e.contentRect.width); });
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);

  const padL = 60, padR = 80, padT = 22, padB = 28;
  const innerW = Math.max(200, w - padL - padR);
  const innerH = height - padT - padB;
  const rowH = Math.max(8, Math.min(14, innerH / Math.max(1, samples.length)));
  const rows = samples.slice(0, Math.floor(innerH / rowH));

  // Find time scale — use max total
  const totals = rows.map(r => r.pipeline_ms.efficientad + r.pipeline_ms.fastsam + r.pipeline_ms.qwen3vl);
  const maxTotal = Math.max(...totals, 2800);
  // ticks at 0, 500, 1000, 1500, 2000, 2500, 3000
  const ticks = [];
  for (let t = 0; t <= maxTotal; t += 500) ticks.push(t);

  const stageColors = ["var(--stage-1)", "var(--stage-2)", "var(--stage-3)"];
  const stageLabels = ["EfficientAD-S", "FastSAM-s", "Qwen3-VL-2B"];

  // Aggregate stats
  const avgs = [0, 1, 2].map(i => {
    const k = ["efficientad", "fastsam", "qwen3vl"][i];
    const sum = rows.reduce((s, r) => s + r.pipeline_ms[k], 0);
    return sum / Math.max(1, rows.length);
  });
  const avgTotal = avgs.reduce((s, x) => s + x, 0);

  const xScale = ms => (ms / maxTotal) * innerW;

  return (
    <div ref={ref} style={{ width: "100%", position: "relative" }}>
      <svg width={w} height={height} viewBox={`0 0 ${w} ${height}`}>
        {/* grid + ticks */}
        {ticks.map((t, i) => {
          const x = padL + xScale(t);
          return (
            <g key={i}>
              <line x1={x} y1={padT} x2={x} y2={padT + innerH}
                    stroke="var(--line-soft)" strokeDasharray={t === 0 ? "0" : "1 3"} />
              <text x={x} y={padT - 8} textAnchor="middle"
                    fill="var(--fg-3)" style={{ fontFamily: "var(--font-mono)", fontSize: 9, letterSpacing: "0.05em" }}>
                {t === 0 ? "0" : `${t}ms`}
              </text>
            </g>
          );
        })}

        {/* row bars */}
        {rows.map((r, i) => {
          const y = padT + i * rowH;
          let acc = 0;
          const segs = [
            { ms: r.pipeline_ms.efficientad, color: "var(--stage-1)" },
            { ms: r.pipeline_ms.fastsam,     color: "var(--stage-2)" },
            { ms: r.pipeline_ms.qwen3vl,     color: "var(--stage-3)" },
          ];
          return (
            <g key={r.id ?? i}>
              {segs.map((s, j) => {
                const x = padL + xScale(acc);
                const ww = xScale(s.ms);
                acc += s.ms;
                return (
                  <rect key={j} x={x} y={y + 1} width={Math.max(0.5, ww)} height={rowH - 2}
                        fill={s.color} opacity={i === 0 ? 1 : 0.85} />
                );
              })}
              {/* row label on left */}
              {i % Math.ceil(rows.length / 6) === 0 && (
                <text x={padL - 8} y={y + rowH / 2 + 3} textAnchor="end"
                      fill="var(--fg-3)" style={{ fontFamily: "var(--font-mono)", fontSize: 9 }}>
                  #{r.id}
                </text>
              )}
              {/* total ms on right */}
              {i < 8 && (
                <text x={padL + xScale(segs[0].ms + segs[1].ms + segs[2].ms) + 6} y={y + rowH / 2 + 3} textAnchor="start"
                      fill={i === 0 ? "var(--fg)" : "var(--fg-3)"}
                      style={{ fontFamily: "var(--font-mono)", fontSize: 9, fontWeight: i === 0 ? 600 : 400 }}>
                  {Math.round(segs[0].ms + segs[1].ms + segs[2].ms)}ms
                </text>
              )}
            </g>
          );
        })}

        {/* "now" line at top */}
        <line x1={padL} y1={padT} x2={padL + innerW} y2={padT}
              stroke="var(--sig-cyan)" strokeWidth="1" opacity="0.4" />

        {/* Average overlay annotations */}
        {(() => {
          let acc = 0;
          return [0, 1, 2].map(i => {
            const x = padL + xScale(acc);
            acc += avgs[i];
            const xEnd = padL + xScale(acc);
            const xMid = (x + xEnd) / 2;
            return (
              <g key={i}>
                <line x1={x} y1={padT + innerH + 4} x2={x} y2={padT + innerH + 10}
                      stroke={stageColors[i]} strokeWidth="1.5" />
                {i === 2 && (
                  <line x1={xEnd} y1={padT + innerH + 4} x2={xEnd} y2={padT + innerH + 10}
                        stroke={stageColors[i]} strokeWidth="1.5" />
                )}
                <text x={xMid} y={padT + innerH + 22} textAnchor="middle"
                      fill={stageColors[i]} style={{ fontFamily: "var(--font-mono)", fontSize: 10, fontWeight: 600 }}>
                  {Math.round(avgs[i])}
                </text>
              </g>
            );
          });
        })()}
      </svg>

      {/* Bottleneck callout */}
      <div style={{
        position: "absolute",
        right: 14, top: 10, width: 220,
        background: "var(--bg-2)",
        border: "1px solid var(--sig-red)",
        padding: "10px 12px",
      }}>
        <div className="eyebrow" style={{ color: "var(--sig-red)", fontSize: 9 }}>⚠ BOTTLENECK DETECTED</div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginTop: 6 }}>
          <span className="mono" style={{ fontSize: 22, fontWeight: 500, color: "var(--fg)" }}>
            {((avgs[2] / avgTotal) * 100).toFixed(1)}<span style={{ fontSize: 12, color: "var(--fg-3)" }}>%</span>
          </span>
        </div>
        <div className="mono" style={{ fontSize: 10, color: "var(--fg-1)", marginTop: 4 }}>
          Qwen3-VL · {Math.round(avgs[2])}ms avg
        </div>
        <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", marginTop: 8, lineHeight: 1.5 }}>
          → opportunity: LoRA short-prompt<br />
          → -45% TTFT (variant B)
        </div>
      </div>

      {/* Stage legend at bottom */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(3, 1fr)",
        borderTop: "1px solid var(--line)",
        marginTop: 4,
      }}>
        {[0, 1, 2].map(i => {
          const k = ["efficientad", "fastsam", "qwen3vl"][i];
          const ms = avgs[i];
          const pct = (ms / avgTotal) * 100;
          const isBottleneck = i === 2;
          return (
            <div key={i} style={{
              padding: "10px 14px",
              borderRight: i < 2 ? "1px solid var(--line)" : "none",
              borderTop: `2px solid ${stageColors[i]}`,
              background: isBottleneck ? "color-mix(in srgb, var(--sig-red) 5%, transparent)" : "transparent",
              position: "relative",
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span className="mono" style={{ fontSize: 9, color: "var(--fg-3)" }}>STAGE {i+1}</span>
                  <span className="mono" style={{ fontSize: 11, color: "var(--fg)", fontWeight: 600 }}>{stageLabels[i]}</span>
                  <INT8Badge />
                </span>
                <span className="mono" style={{ fontSize: 9, color: isBottleneck ? "var(--sig-red)" : "var(--fg-3)", fontWeight: 600 }}>
                  {pct.toFixed(1)}%
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginTop: 8 }}>
                <span className="mono" style={{
                  fontSize: 22, fontWeight: 500, color: stageColors[i],
                  fontVariantNumeric: "tabular-nums",
                }}>{ms < 100 ? ms.toFixed(1) : Math.round(ms)}</span>
                <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>ms · avg</span>
              </div>
              <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", marginTop: 4 }}>
                {i === 0 && "PDN · 256×256 · NPU core 0"}
                {i === 1 && "YOLOv8-seg · 640×640 · NPU 1"}
                {i === 2 && `W8A8 · prompt+decode · NPU 2`}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

Object.assign(window, { PipelineWaterfall });
