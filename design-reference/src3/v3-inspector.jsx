// Active Frame Inspector — shows the most recent completed defect with streaming VLM JSON.
const { useState: _isS, useEffect: _isE, useRef: _isR } = React;

function FrameInspector({ defect }){
  if (!defect) {
    return (
      <div style={{
        background: "var(--bg-1)", border: "1px solid var(--line)", padding: 40,
        textAlign: "center", color: "var(--fg-3)",
      }}>
        <span className="mono" style={{ fontSize: 12 }}>Waiting for first frame…</span>
      </div>
    );
  }

  return (
    <div style={{
      background: "var(--bg-1)", border: "1px solid var(--line)",
      display: "grid", gridTemplateColumns: "minmax(0,1.1fr) minmax(0,1fr)",
    }}>
      <FramePane defect={defect} />
      <JsonPane defect={defect} />
    </div>
  );
}

function FramePane({ defect }){
  return (
    <div style={{ padding: 18, borderRight: "1px solid var(--line)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 12 }}>
        <div>
          <div className="eyebrow">LAST FRAME · {defect.line_id}</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 4 }}>
            <span className="mono" style={{ fontSize: 18, color: "var(--fg)", fontWeight: 600 }}>#{defect.id}</span>
            <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>
              · {fmtTime(defect.edge_ts)}
            </span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <SevPill value={defect.severity} />
          <CatPill value={defect.category} />
          <VarPill value={defect.variant} />
        </div>
      </div>

      {/* Frame canvas */}
      <div style={{
        position: "relative", width: "100%", aspectRatio: "4/3",
        background: "var(--bg)", border: "1px solid var(--line)",
        overflow: "hidden",
      }}>
        {/* simulated content */}
        <SimulatedSample category={defect.category} />

        {/* scan line */}
        <div style={{
          position: "absolute", left: 0, right: 0, top: 0, height: 2,
          background: "linear-gradient(90deg, transparent, var(--acc), transparent)",
          opacity: 0.5,
          animation: "scan-line 4s linear infinite",
        }} />

        {/* corner readouts */}
        <div style={{
          position: "absolute", top: 8, left: 10,
          fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--acc)",
          letterSpacing: "0.1em", textShadow: "0 0 6px var(--acc-glow)",
        }}>
          CAM-{defect.line_id} · 1280×1024
        </div>
        <div style={{
          position: "absolute", top: 8, right: 10,
          fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--warn)",
        }}>
          σ = {defect.anomaly_score}
        </div>
        <div style={{
          position: "absolute", bottom: 8, left: 10,
          fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--fg-2)",
        }}>
          {defect.image_url.split("/").slice(-1)[0]}
        </div>
        <div style={{
          position: "absolute", bottom: 8, right: 10,
          display: "flex", alignItems: "center", gap: 5,
          fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--ok)",
        }}>
          <span style={{
            width: 5, height: 5, background: "var(--ok)", borderRadius: "50%",
            animation: "pulse-dot 1.4s infinite",
          }} />
          REC
        </div>

        {/* bboxes */}
        <svg viewBox="0 0 100 100" preserveAspectRatio="none"
             style={{ position: "absolute", inset: 0, width: "100%", height: "100%", overflow: "visible" }}>
          {defect.bboxes.map((b, i) => {
            const x = b.x * 100, y = b.y * 100, w = b.w * 100, h = b.h * 100;
            const c = "var(--acc)";
            return (
              <g key={i}>
                <rect x={x} y={y} width={w} height={h}
                      fill={`color-mix(in srgb, ${c} 8%, transparent)`}
                      stroke={c} strokeWidth="0.2" vectorEffect="non-scaling-stroke"
                      style={{ animation: "slide-in-up 0.35s ease-out backwards", animationDelay: `${i * 0.08}s` }} />
                {/* corner ticks */}
                {[
                  [x, y+1.5, x, y, x+1.5, y],
                  [x+w-1.5, y, x+w, y, x+w, y+1.5],
                  [x, y+h-1.5, x, y+h, x+1.5, y+h],
                  [x+w-1.5, y+h, x+w, y+h, x+w, y+h-1.5],
                ].map((pts, j) => (
                  <polyline key={j} points={pts.map(v=>v).join(" ")}
                            fill="none" stroke={c} strokeWidth="0.5" vectorEffect="non-scaling-stroke" />
                ))}
                <foreignObject x={x} y={Math.max(0, y - 4)} width={Math.max(w, 20)} height="4">
                  <div xmlns="http://www.w3.org/1999/xhtml" style={{
                    display: "inline-block",
                    fontFamily: "var(--font-mono)", fontSize: 8,
                    color: "var(--bg)", background: c, padding: "1px 4px",
                    letterSpacing: "0.06em", fontWeight: 700,
                  }}>{defect.defect_type}<span style={{ opacity: 0.6, marginLeft: 4 }}>{(defect.confidence*100).toFixed(0)}</span></div>
                </foreignObject>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Per-stage gantt for this frame */}
      <div style={{ marginTop: 14 }}>
        <div className="eyebrow" style={{ marginBottom: 6 }}>
          PIPELINE BREAKDOWN · {Math.round(defect.pipeline_ms.efficientad + defect.pipeline_ms.fastsam + defect.pipeline_ms.qwen3vl)} ms
        </div>
        <FrameGantt defect={defect} />
      </div>
    </div>
  );
}

function FrameGantt({ defect }){
  const stages = [
    { k: "efficientad", color: "var(--core-0)", ms: defect.pipeline_ms.efficientad, label: "EfficientAD" },
    { k: "fastsam",     color: "var(--core-1)", ms: defect.pipeline_ms.fastsam,     label: "FastSAM" },
    { k: "qwen3vl",     color: "var(--core-2)", ms: defect.pipeline_ms.qwen3vl,     label: "Qwen3-VL" },
  ];
  const total = stages.reduce((s, x) => s + x.ms, 0);
  return (
    <div>
      <div style={{ display: "flex", height: 8, border: "1px solid var(--line)", overflow: "hidden", background: "var(--bg-3)" }}>
        {stages.map(s => (
          <div key={s.k} title={`${s.label}: ${s.ms.toFixed(1)} ms`} style={{
            width: `${(s.ms / total) * 100}%`,
            background: s.color,
            boxShadow: `inset 0 0 4px color-mix(in srgb, ${s.color} 70%, black)`,
          }} />
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", marginTop: 8, gap: 8 }}>
        {stages.map(s => (
          <div key={s.k} style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span style={{ width: 6, height: 6, background: s.color, borderRadius: "50%" }} />
            <span style={{ fontSize: 11, color: "var(--fg-2)" }}>{s.label}</span>
            <span className="mono" style={{ fontSize: 11, color: "var(--fg)", marginLeft: "auto" }}>
              {s.ms < 100 ? s.ms.toFixed(1) : Math.round(s.ms)}<span style={{ color: "var(--fg-3)" }}>ms</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function JsonPane({ defect }){
  const json = useStreamingJson(defect);
  const lines = json.text.split("\n");
  return (
    <div style={{
      padding: 18, background: "linear-gradient(180deg, var(--bg-1) 0%, #0d0d12 100%)",
      display: "flex", flexDirection: "column", gap: 12,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div>
          <div className="eyebrow">VLM OUTPUT · Qwen3-VL-2B</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 4 }}>
            <span style={{ fontSize: 14, color: "var(--fg)", fontWeight: 500 }}>Streaming JSON</span>
            <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>· prompt+decode</span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 14 }}>
          <Metric label="TTFT" value={defect.vlm_metrics.ttft_ms} unit="ms"
                  color={defect.variant === "B" ? "var(--ab-b)" : "var(--ab-a)"} />
          <Metric label="DECODE" value={defect.vlm_metrics.decode_tps.toFixed(1)} unit="tok/s"
                  color="var(--acc)" />
          <Metric label="OUT TOK" value={defect.vlm_metrics.output_tokens} />
        </div>
      </div>

      <div style={{
        flex: 1, position: "relative",
        background: "#08080c",
        border: "1px solid var(--line)",
        padding: "14px 16px",
        fontFamily: "var(--font-mono)", fontSize: 12, lineHeight: 1.7,
        minHeight: 320, overflow: "hidden",
      }}>
        {/* terminal header strip */}
        <div style={{
          position: "absolute", top: 0, left: 0, right: 0, height: 22,
          background: "var(--bg-2)", borderBottom: "1px solid var(--line-soft)",
          display: "flex", alignItems: "center", padding: "0 10px", gap: 5,
        }}>
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#ff6378" }} />
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#ffbf5c" }} />
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#6dffac" }} />
          <span className="mono" style={{
            marginLeft: 10, fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.1em",
          }}>vlm_output.json · LIVE</span>
          <span style={{ flex: 1 }} />
          <span className="mono" style={{ fontSize: 9, color: json.done ? "var(--ok)" : "var(--warn)" }}>
            {json.done ? "✓ parsed" : "● streaming"}
          </span>
        </div>
        <pre style={{ margin: 0, paddingTop: 18, color: "var(--fg-1)", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
          {lines.map((line, i) => (
            <div key={i} style={{ display: "flex" }}>
              <span style={{ width: 28, color: "var(--fg-4)", textAlign: "right", paddingRight: 10, userSelect: "none" }}>
                {String(i + 1).padStart(2, " ")}
              </span>
              <span style={{ flex: 1 }} dangerouslySetInnerHTML={{ __html: highlightJson(line) }} />
            </div>
          ))}
          {!json.done && <span style={{
            display: "inline-block", width: 8, height: 12, marginLeft: 38,
            background: "var(--acc)", verticalAlign: "middle",
            animation: "blink-cursor 0.8s infinite",
          }} />}
        </pre>
      </div>
    </div>
  );
}

function useStreamingJson(defect){
  const target = JSON.stringify({
    category: defect.category,
    defect_type: defect.defect_type,
    severity: defect.severity,
    confidence: defect.confidence,
    bboxes: defect.bboxes.map(b => ({
      x: +b.x.toFixed(3), y: +b.y.toFixed(3),
      w: +b.w.toFixed(3), h: +b.h.toFixed(3),
    })),
    description: defect.description,
  }, null, 2);
  const [pos, setPos] = _isS(0);
  _isE(() => {
    setPos(0);
    let p = 0;
    const id = setInterval(() => {
      p += Math.floor(3 + Math.random() * 4);
      if (p >= target.length){
        setPos(target.length);
        clearInterval(id);
      } else {
        setPos(p);
      }
    }, 24);
    return () => clearInterval(id);
  }, [defect.id]);
  return { text: target.slice(0, pos), done: pos >= target.length };
}

function highlightJson(line){
  return line
    .replace(/("(?:[^"\\]|\\.)*"):/g, '<span style="color: var(--ab-b);">$1</span>:')
    .replace(/: ("(?:[^"\\]|\\.)*")/g, ': <span style="color: var(--acc);">$1</span>')
    .replace(/: (-?\d+\.?\d*)/g, ': <span style="color: var(--core-1);">$1</span>')
    .replace(/: (true|false|null)/g, ': <span style="color: var(--ab-a);">$1</span>');
}

// ----- sample image placeholders -----
function SimulatedSample({ category }){
  // Stylized SVG illustration of the sample type
  if (category === "metal_nut") return <NutSample />;
  if (category === "screw")     return <ScrewSample />;
  if (category === "pill")      return <PillSample />;
  return null;
}

function NutSample(){
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <defs>
        <radialGradient id="nut-g" cx="50%" cy="50%">
          <stop offset="0%" stopColor="#3a3a48" />
          <stop offset="100%" stopColor="#1a1a25" />
        </radialGradient>
      </defs>
      <rect width="200" height="150" fill="#0e0e15" />
      {/* hex nut shape */}
      <polygon points="100,40 140,60 140,100 100,120 60,100 60,60"
               fill="url(#nut-g)" stroke="#4a4a5a" strokeWidth="0.8" />
      <circle cx="100" cy="80" r="14" fill="#0a0a10" stroke="#3a3a48" strokeWidth="0.8" />
      {/* highlights */}
      <line x1="65" y1="62" x2="95" y2="44" stroke="#5a5a6a" strokeWidth="0.5" opacity="0.6" />
      <line x1="135" y1="62" x2="105" y2="44" stroke="#5a5a6a" strokeWidth="0.5" opacity="0.4" />
    </svg>
  );
}
function ScrewSample(){
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <rect width="200" height="150" fill="#0e0e15" />
      <ellipse cx="100" cy="40" rx="22" ry="6" fill="#3a3a48" stroke="#4a4a5a" strokeWidth="0.5" />
      <rect x="92" y="42" width="16" height="80" fill="#2a2a35" stroke="#4a4a5a" strokeWidth="0.5" />
      {Array.from({length: 12}).map((_, i) => (
        <line key={i} x1="92" y1={48 + i*6} x2="108" y2={50 + i*6} stroke="#5a5a6a" strokeWidth="0.4" />
      ))}
      <polygon points="92,122 108,122 100,134" fill="#3a3a48" />
    </svg>
  );
}
function PillSample(){
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <defs>
        <linearGradient id="pill-g" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#5a5a6a" />
          <stop offset="100%" stopColor="#2a2a35" />
        </linearGradient>
      </defs>
      <rect width="200" height="150" fill="#0e0e15" />
      <rect x="55" y="65" width="90" height="28" rx="14" fill="url(#pill-g)" stroke="#4a4a5a" strokeWidth="0.5" />
      <line x1="100" y1="65" x2="100" y2="93" stroke="#1a1a25" strokeWidth="0.8" />
      {/* imprint */}
      <text x="80" y="84" fontFamily="JetBrains Mono" fontSize="8" fill="#1a1a25">M</text>
      <text x="115" y="84" fontFamily="JetBrains Mono" fontSize="8" fill="#1a1a25">8</text>
    </svg>
  );
}

function Metric({ label, value, unit, color = "var(--fg-1)" }){
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
      <span className="eyebrow" style={{ fontSize: 9 }}>{label}</span>
      <span style={{ display: "flex", alignItems: "baseline", gap: 3, marginTop: 2 }}>
        <span className="mono" style={{ fontSize: 16, color, fontWeight: 500 }}>{value}</span>
        {unit && <span className="mono" style={{ fontSize: 9, color: "var(--fg-3)" }}>{unit}</span>}
      </span>
    </div>
  );
}

function SevPill({ value }){
  const c = { low: "var(--ok)", medium: "var(--warn)", high: "var(--crit)" }[value];
  const l = { low: "LOW", medium: "MED", high: "HIGH" }[value];
  return <span className="mono" style={{ fontSize: 10, padding: "2px 8px", border: `1px solid ${c}`, color: c, letterSpacing: "0.12em", fontWeight: 600, background: `color-mix(in srgb, ${c} 14%, transparent)` }}>{l}</span>;
}
function CatPill({ value }){
  const m = { metal_nut: { c: "var(--core-0)", l: "MN" }, screw: { c: "#f472b6", l: "SCR" }, pill: { c: "var(--core-1)", l: "PIL" } }[value];
  return <span className="mono" style={{ fontSize: 10, padding: "2px 8px", border: `1px solid ${m.c}`, color: m.c, letterSpacing: "0.08em", fontWeight: 600 }}>{m.l}</span>;
}
function VarPill({ value }){
  const c = value === "A" ? "var(--ab-a)" : "var(--ab-b)";
  return <span className="mono" style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 22, height: 22, border: `1px solid ${c}`, color: c, fontSize: 11, fontWeight: 700, background: `color-mix(in srgb, ${c} 14%, transparent)` }}>{value}</span>;
}

Object.assign(window, { FrameInspector, SevPill, CatPill, VarPill, SimulatedSample });
