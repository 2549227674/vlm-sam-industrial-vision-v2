// V2 charts — Throughput sparkline, NPU utilization bars, Severity breakdown.

const { useEffect: _v2cE, useRef: _v2cR, useState: _v2cS } = React;

function ThroughputChart({ buckets, height = 140, accent = "var(--sig-cyan)" }){
  const ref = _v2cR(null);
  const [w, setW] = _v2cS(700);
  _v2cE(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(es => { for (const e of es) setW(e.contentRect.width); });
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  const padL = 36, padR = 12, padT = 14, padB = 22;
  const innerW = Math.max(80, w - padL - padR);
  const innerH = height - padT - padB;
  const max = Math.max(...buckets.map(b => b.count), 1);
  const barW = innerW / buckets.length;
  return (
    <div ref={ref} style={{ width: "100%" }}>
      <svg width={w} height={height} viewBox={`0 0 ${w} ${height}`}>
        {[0, 0.5, 1].map((p, i) => {
          const y = padT + (1 - p) * innerH;
          return (
            <g key={i}>
              <line x1={padL} y1={y} x2={padL + innerW} y2={y}
                    stroke="var(--line-soft)" strokeDasharray={p === 0 ? "0" : "1 3"} />
              <text x={padL - 6} y={y + 3} textAnchor="end"
                    fill="var(--fg-3)" style={{ fontFamily: "var(--font-mono)", fontSize: 9 }}>
                {Math.round(max * p)}
              </text>
            </g>
          );
        })}
        {buckets.map((b, i) => {
          const h = (b.count / max) * innerH;
          const x = padL + i * barW;
          const y = padT + innerH - h;
          const isHi = b.hi > 0;
          return (
            <g key={i}>
              <rect x={x + 1} y={y} width={Math.max(1, barW - 2)} height={h}
                    fill={isHi ? "var(--sig-red)" : accent} opacity={i === buckets.length - 1 ? 1 : 0.7} />
              {b.hi > 0 && (
                <rect x={x + 1} y={y} width={Math.max(1, barW - 2)} height={Math.min(h, (b.hi / b.count) * h)}
                      fill="var(--sig-red)" />
              )}
            </g>
          );
        })}
        {buckets.map((b, i) => {
          if (i % 4 !== 0 && i !== buckets.length - 1) return null;
          const x = padL + i * barW + barW / 2;
          return (
            <text key={i} x={x} y={height - 6} textAnchor="middle"
                  fill="var(--fg-3)" style={{ fontFamily: "var(--font-mono)", fontSize: 9 }}>
              {String(b.ts.getHours()).padStart(2, "0")}:00
            </text>
          );
        })}
        {/* live cursor */}
        <line x1={padL + innerW - 1} y1={padT} x2={padL + innerW - 1} y2={padT + innerH}
              stroke={accent} strokeWidth="1" opacity="0.6" strokeDasharray="2 2" />
      </svg>
    </div>
  );
}

function NPUUtilization({ frames, qps }){
  // 3 NPU cores: roughly mapped to stages — show as horizontal scrolling bars
  const cores = [
    { id: 0, name: "NPU CORE 0", load: 18 + (Math.sin(Date.now() / 800) * 8 + 8),  task: "EfficientAD-S",  color: "var(--stage-1)" },
    { id: 1, name: "NPU CORE 1", load: 42 + (Math.sin(Date.now() / 600) * 12 + 8), task: "FastSAM-s",      color: "var(--stage-2)" },
    { id: 2, name: "NPU CORE 2", load: 78 + (Math.sin(Date.now() / 1100) * 8 + 8), task: "Qwen3-VL-2B",    color: "var(--stage-3)" },
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {cores.map(c => (
        <div key={c.id}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
            <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.12em" }}>{c.name}</span>
              <span className="mono" style={{ fontSize: 11, color: "var(--fg-1)" }}>{c.task}</span>
            </span>
            <span className="mono" style={{ fontSize: 13, color: c.color, fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
              {Math.round(c.load)}<span style={{ color: "var(--fg-3)", fontSize: 10 }}>%</span>
            </span>
          </div>
          <div style={{ height: 8, background: "var(--bg-3)", border: "1px solid var(--line-soft)", position: "relative", overflow: "hidden" }}>
            <div style={{
              width: `${c.load}%`, height: "100%", background: c.color,
              boxShadow: `0 0 8px ${c.color}`, transition: "width 0.5s",
            }} />
            <div style={{
              position: "absolute", inset: 0,
              background: "repeating-linear-gradient(90deg, transparent 0, transparent 9px, rgba(0,0,0,0.15) 9px, rgba(0,0,0,0.15) 10px)",
              pointerEvents: "none",
            }} />
          </div>
        </div>
      ))}
      <div style={{
        marginTop: 6, paddingTop: 10, borderTop: "1px dashed var(--line-soft)",
        display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12,
      }}>
        <div>
          <div className="eyebrow" style={{ fontSize: 9 }}>SoC TEMP</div>
          <div className="mono" style={{ fontSize: 14, color: "var(--sig-amber)", marginTop: 2 }}>62.4<span style={{ color: "var(--fg-3)", fontSize: 10 }}>°C</span></div>
        </div>
        <div>
          <div className="eyebrow" style={{ fontSize: 9 }}>POWER</div>
          <div className="mono" style={{ fontSize: 14, color: "var(--fg)", marginTop: 2 }}>4.8<span style={{ color: "var(--fg-3)", fontSize: 10 }}>W</span></div>
        </div>
        <div>
          <div className="eyebrow" style={{ fontSize: 9 }}>LPDDR4</div>
          <div className="mono" style={{ fontSize: 14, color: "var(--fg)", marginTop: 2 }}>9.2<span style={{ color: "var(--fg-3)", fontSize: 10 }}>/16 GB</span></div>
        </div>
      </div>
    </div>
  );
}

function CategorySeverityMatrix({ stats }){
  const cats = ["metal_nut", "screw", "pill"];
  const sevs = ["low", "medium", "high"];
  // distribute stats — synthetic per-cat-sev
  const grid = {};
  let total = 0;
  for (const c of cats){
    grid[c] = {};
    for (const s of sevs){
      const v = Math.floor((stats.by_category[c] / 3) * (s === "high" ? 0.18 : s === "medium" ? 0.30 : 0.52) + Math.random() * 6);
      grid[c][s] = v;
      total += v;
    }
  }
  const max = Math.max(...cats.flatMap(c => sevs.map(s => grid[c][s])), 1);
  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "auto repeat(3, 1fr)", gap: 1, background: "var(--line)" }}>
        <div style={{ background: "var(--bg-1)" }} />
        {sevs.map(s => (
          <div key={s} style={{
            background: "var(--bg-2)", padding: "8px 10px", textAlign: "center",
          }}>
            <SeverityChip value={s} size="sm" />
          </div>
        ))}
        {cats.map(c => (
          <React.Fragment key={c}>
            <div style={{
              background: "var(--bg-2)", padding: "10px 12px", display: "flex", alignItems: "center", gap: 8,
            }}>
              <CategoryChip value={c} />
              <span className="mono" style={{ fontSize: 11, color: "var(--fg-1)" }}>{c}</span>
            </div>
            {sevs.map(s => {
              const v = grid[c][s];
              const intensity = v / max;
              const color = s === "high" ? "var(--sev-high)" : s === "medium" ? "var(--sev-med)" : "var(--sev-low)";
              return (
                <div key={s} style={{
                  background: `color-mix(in srgb, ${color} ${intensity * 50}%, var(--bg-1))`,
                  padding: "14px 12px", textAlign: "center", position: "relative",
                }}>
                  <span className="mono" style={{
                    fontSize: 17, color: intensity > 0.7 ? "var(--bg-0)" : "var(--fg)",
                    fontVariantNumeric: "tabular-nums", fontWeight: 600,
                  }}>{v}</span>
                </div>
              );
            })}
          </React.Fragment>
        ))}
      </div>
      <div style={{
        marginTop: 12, display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>category × severity · last 24h</span>
        <span className="mono" style={{ fontSize: 10, color: "var(--fg-1)" }}>Σ = {total}</span>
      </div>
    </div>
  );
}

Object.assign(window, { ThroughputChart, NPUUtilization, CategorySeverityMatrix });
