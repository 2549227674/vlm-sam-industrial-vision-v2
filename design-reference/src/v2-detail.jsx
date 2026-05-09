// V2 Detail panel — opens inline as right-side drawer / focus view.

const { useState: _vdS, useEffect: _vdE } = React;

function DetailDrawer({ defect, onClose }){
  if (!defect) return null;
  const total = Math.round(defect.pipeline_ms.efficientad + defect.pipeline_ms.fastsam + defect.pipeline_ms.qwen3vl);
  const stages = [
    { k: "efficientad", name: "EfficientAD-S", color: "var(--stage-1)" },
    { k: "fastsam",     name: "FastSAM-s",     color: "var(--stage-2)" },
    { k: "qwen3vl",     name: "Qwen3-VL-2B",   color: "var(--stage-3)" },
  ];

  return (
    <div style={{
      background: "var(--bg-1)", border: "1px solid var(--line)",
      display: "flex", flexDirection: "column",
    }}>
      {/* Header */}
      <div style={{
        padding: "10px 14px", borderBottom: "1px solid var(--line)",
        background: "var(--bg-2)",
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="mono" style={{ color: "var(--sig-cyan)", fontSize: 11, fontWeight: 700 }}>
            DEFECT #{defect.id}
          </span>
          <span style={{ width: 1, height: 12, background: "var(--line)" }} />
          <CategoryChip value={defect.category} />
          <SeverityChip value={defect.severity} size="sm" />
          <VariantChip value={defect.variant} size="sm" />
        </div>
        <button onClick={onClose}
          style={{
            background: "transparent", border: "1px solid var(--line)",
            color: "var(--fg-2)", fontFamily: "var(--font-mono)", fontSize: 10,
            padding: "2px 8px", cursor: "pointer", letterSpacing: "0.1em",
          }}>CLOSE ESC</button>
      </div>

      {/* Frame + bbox */}
      <div style={{ padding: 14 }}>
        <DefectFrame defect={defect} />
      </div>

      {/* Sections */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "var(--line)" }}>
        <DetailSection title="VLM OUTPUT" subtitle="parsed JSON">
          <pre className="mono" style={{
            margin: 0, fontSize: 11, color: "var(--fg-1)", lineHeight: 1.6,
            whiteSpace: "pre-wrap", wordBreak: "break-word",
          }}>{JSON.stringify({
            category: defect.category,
            defect_type: defect.defect_type,
            severity: defect.severity,
            confidence: defect.confidence,
            bboxes: defect.bboxes.map(b => ({
              x: +b.x.toFixed(3), y: +b.y.toFixed(3),
              w: +b.w.toFixed(3), h: +b.h.toFixed(3),
            })),
            description: defect.description,
          }, null, 2)}</pre>
        </DetailSection>

        <DetailSection title="VLM METRICS" subtitle={`variant ${defect.variant}`}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", rowGap: 10 }}>
            <KV label="TTFT"          value={defect.vlm_metrics.ttft_ms} unit="ms" tone={defect.variant === "B" ? "teal" : "violet"} />
            <KV label="DECODE"        value={defect.vlm_metrics.decode_tps.toFixed(2)} unit="tok/s" />
            <KV label="PROMPT TOK"    value={defect.vlm_metrics.prompt_tokens} />
            <KV label="OUTPUT TOK"    value={defect.vlm_metrics.output_tokens} />
            <KV label="RSS"           value={defect.vlm_metrics.rss_mb} unit="MB" />
            <KV label="JSON PARSE"
                value={defect.vlm_metrics.json_parse_ok ? "OK" : "FAIL"}
                tone={defect.vlm_metrics.json_parse_ok ? "green" : "red"} />
          </div>
        </DetailSection>
      </div>

      {/* Pipeline gantt */}
      <div style={{
        padding: "12px 14px", borderTop: "1px solid var(--line)",
      }}>
        <div className="eyebrow" style={{ marginBottom: 8 }}>3-STAGE PIPELINE · TOTAL {total}ms</div>
        <div style={{ position: "relative", height: 22, background: "var(--bg-3)", border: "1px solid var(--line-soft)" }}>
          {(() => {
            let acc = 0;
            return stages.map(s => {
              const ms = defect.pipeline_ms[s.k];
              const x = (acc / total) * 100;
              const w = (ms / total) * 100;
              acc += ms;
              return (
                <div key={s.k} style={{
                  position: "absolute", top: 0, left: `${x}%`, width: `${w}%`, height: "100%",
                  background: s.color, opacity: 0.85,
                  borderRight: "1px solid var(--bg-0)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  overflow: "hidden",
                }}>
                  {w > 8 && (
                    <span className="mono" style={{ fontSize: 10, color: "var(--bg-0)", fontWeight: 700 }}>
                      {ms < 100 ? ms.toFixed(1) : Math.round(ms)}
                    </span>
                  )}
                </div>
              );
            });
          })()}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", marginTop: 6 }}>
          {stages.map(s => (
            <div key={s.k} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 8, height: 8, background: s.color }} />
              <span className="mono" style={{ fontSize: 9, color: "var(--fg-3)" }}>{s.name}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Provenance footer */}
      <div style={{
        padding: "10px 14px", background: "var(--bg-2)", borderTop: "1px solid var(--line)",
        display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 6,
        fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--fg-3)",
      }}>
        <div>line_id <span style={{ color: "var(--fg-1)" }}>{defect.line_id}</span></div>
        <div>edge_ts <span style={{ color: "var(--fg-1)" }}>{fmtDateTime(defect.edge_ts)}</span></div>
        <div>image_url <span style={{ color: "var(--fg-1)" }}>…/{defect.image_url.split("/").slice(-1)[0]}</span></div>
        <div>anomaly_score <span style={{ color: "var(--sig-amber)" }}>{defect.anomaly_score}</span></div>
      </div>
    </div>
  );
}

function DefectFrame({ defect }){
  const W = 480, H = 320;
  return (
    <div style={{
      position: "relative", width: "100%", aspectRatio: "3/2",
      background: "var(--bg-0)", border: "1px solid var(--line)",
      overflow: "hidden",
    }} className="scan-bg">
      {/* simulated frame content */}
      <div className="stripe-bg" style={{
        position: "absolute", inset: "12% 18%",
        opacity: 0.6,
      }} />
      {/* overlay corner readouts */}
      <div style={{
        position: "absolute", top: 8, left: 10,
        fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--sig-cyan)",
        letterSpacing: "0.1em",
      }}>
        CAM-{defect.line_id} · 1280×1024 · {fmtTime(defect.edge_ts)}
      </div>
      <div style={{
        position: "absolute", top: 8, right: 10,
        fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--sig-amber)",
      }}>
        ANOMALY {defect.anomaly_score} · σ
      </div>
      <div style={{
        position: "absolute", bottom: 8, left: 10,
        fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--fg-2)",
      }}>
        {defect.image_url.split("/").slice(-1)[0]}
      </div>
      <div style={{
        position: "absolute", bottom: 8, right: 10,
        display: "flex", alignItems: "center", gap: 6,
        fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--sig-green)",
      }}>
        <span style={{ width: 5, height: 5, background: "var(--sig-green)", borderRadius: "50%", animation: "pulse-dot 1.4s infinite" }} />
        REC
      </div>

      {/* bboxes */}
      <svg viewBox="0 0 100 100" preserveAspectRatio="none"
           style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
        {defect.bboxes.map((b, i) => {
          const c = defect.severity === "high" ? "var(--sev-high)"
                  : defect.severity === "medium" ? "var(--sev-med)" : "var(--sev-low)";
          const x = b.x * 100, y = b.y * 100, w = b.w * 100, h = b.h * 100;
          const tick = 1.6;
          return (
            <g key={i}>
              {/* corner ticks */}
              <polyline points={`${x},${y+tick} ${x},${y} ${x+tick},${y}`} stroke={c} strokeWidth="0.3" fill="none" vectorEffect="non-scaling-stroke" />
              <polyline points={`${x+w-tick},${y} ${x+w},${y} ${x+w},${y+tick}`} stroke={c} strokeWidth="0.3" fill="none" vectorEffect="non-scaling-stroke" />
              <polyline points={`${x},${y+h-tick} ${x},${y+h} ${x+tick},${y+h}`} stroke={c} strokeWidth="0.3" fill="none" vectorEffect="non-scaling-stroke" />
              <polyline points={`${x+w-tick},${y+h} ${x+w},${y+h} ${x+w},${y+h-tick}`} stroke={c} strokeWidth="0.3" fill="none" vectorEffect="non-scaling-stroke" />
              <rect x={x} y={y} width={w} height={h}
                    fill="none" stroke={c} strokeWidth="0.15" strokeDasharray="0.6 0.4"
                    vectorEffect="non-scaling-stroke" opacity={0.6} />
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function DetailSection({ title, subtitle, children }){
  return (
    <div style={{ padding: "12px 14px", background: "var(--bg-1)" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 8 }}>
        <span className="eyebrow">{title}</span>
        {subtitle && <span className="mono" style={{ fontSize: 9, color: "var(--fg-3)" }}>· {subtitle}</span>}
      </div>
      {children}
    </div>
  );
}

function KV({ label, value, unit, tone = "default" }){
  const c = { default: "var(--fg)", cyan: "var(--sig-cyan)", green: "var(--sig-green)",
              amber: "var(--sig-amber)", red: "var(--sig-red)",
              violet: "var(--sig-violet)", teal: "var(--sig-teal)" }[tone];
  return (
    <div>
      <div className="eyebrow" style={{ fontSize: 9 }}>{label}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginTop: 2 }}>
        <span className="mono" style={{ fontSize: 16, color: c, fontWeight: 500, fontVariantNumeric: "tabular-nums" }}>{value}</span>
        {unit && <span className="mono" style={{ fontSize: 9, color: "var(--fg-3)" }}>{unit}</span>}
      </div>
    </div>
  );
}

Object.assign(window, { DetailDrawer });
