// V4 Frame Inspector — left: frame + bboxes, right: tabbed pane (JSON / Metrics / Provenance)
// Plus shared mini-frame canvas, severity/category/variant pills.

const { useState: _isS, useEffect: _isE, useRef: _isR } = React;

function FrameInspector({ defect }){
  const [tab, setTab] = _isS("json");
  if (!defect){
    return (
      <div style={{
        background: "var(--bg-1)", border: "1px solid var(--line)", padding: 40,
        textAlign: "center", color: "var(--fg-3)",
      }}>
        <span className="mono" style={{ fontSize: 12 }}>等待首帧…</span>
      </div>
    );
  }
  return (
    <div style={{
      background: "var(--bg-1)", border: "1px solid var(--line)",
      display: "grid", gridTemplateColumns: "minmax(0,1.1fr) minmax(0,1fr)",
    }}>
      <FramePane defect={defect} />
      <RightPane defect={defect} tab={tab} setTab={setTab} />
    </div>
  );
}

function FramePane({ defect }){
  return (
    <div style={{ padding: 18, borderRight: "1px solid var(--line)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 12 }}>
        <div>
          <div className="eyebrow">最新帧 · {defect.line_id}</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 4 }}>
            <span className="mono" style={{ fontSize: 18, color: "var(--fg)", fontWeight: 600 }}>#{defect.id}</span>
            <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>· {fmtTime(defect.edge_ts)}</span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap", justifyContent: "flex-end" }}>
          <SevPill value={defect.severity} />
          <CatPill value={defect.category} />
          <VariantPill value={defect.variant} />
        </div>
      </div>

      <FrameCanvas defect={defect} cornerLabels />

      <div style={{ marginTop: 14 }}>
        <div className="eyebrow" style={{ marginBottom: 6 }}>
          流水线耗时 · {Math.round(defect.pipeline_ms.efficientad + defect.pipeline_ms.fastsam + defect.pipeline_ms.qwen3vl)} ms
        </div>
        <FrameGantt defect={defect} />
      </div>
    </div>
  );
}

// ── Shared frame canvas (reused in drawer + cards) ───────────────────────
function FrameCanvas({ defect, cornerLabels = false, aspect = "4/3" }){
  return (
    <div style={{
      position: "relative", width: "100%", aspectRatio: aspect,
      background: "var(--bg)", border: "1px solid var(--line)", overflow: "hidden",
    }}>
      <SimulatedSample category={defect.category} />

      {/* scan line */}
      <div style={{
        position: "absolute", left: 0, right: 0, top: 0, height: 2,
        background: "linear-gradient(90deg, transparent, var(--acc), transparent)",
        opacity: 0.5, animation: "scan-line 4s linear infinite",
      }} />

      {cornerLabels && (
        <>
          <div style={{ position: "absolute", top: 8, left: 10,
                        fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--acc)",
                        letterSpacing: "0.1em", textShadow: "0 0 6px var(--acc-glow)" }}>
            CAM-{defect.line_id} · 1280×1024
          </div>
          <div style={{ position: "absolute", top: 8, right: 10,
                        fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--warn)" }}>
            σ = {defect.anomaly_score}
          </div>
          <div style={{ position: "absolute", bottom: 8, left: 10,
                        fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--fg-2)" }}>
            {defect.image_url.split("/").slice(-1)[0]}
          </div>
          <div style={{ position: "absolute", bottom: 8, right: 10,
                        display: "flex", alignItems: "center", gap: 5,
                        fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--ok)" }}>
            <span style={{ width: 5, height: 5, background: "var(--ok)", borderRadius: "50%",
                           animation: "pulse-dot 1.4s infinite" }} />
            REC
          </div>
        </>
      )}

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
              {[
                [x, y+1.5, x, y, x+1.5, y],
                [x+w-1.5, y, x+w, y, x+w, y+1.5],
                [x, y+h-1.5, x, y+h, x+1.5, y+h],
                [x+w-1.5, y+h, x+w, y+h, x+w, y+h-1.5],
              ].map((pts, j) => (
                <polyline key={j} points={pts.join(" ")}
                          fill="none" stroke={c} strokeWidth="0.5" vectorEffect="non-scaling-stroke" />
              ))}
              {cornerLabels && (
                <foreignObject x={x} y={Math.max(0, y - 4)} width={Math.max(w, 20)} height="4">
                  <div xmlns="http://www.w3.org/1999/xhtml" style={{
                    display: "inline-block",
                    fontFamily: "var(--font-mono)", fontSize: 8,
                    color: "var(--bg)", background: c, padding: "1px 4px",
                    letterSpacing: "0.06em", fontWeight: 700,
                  }}>{defect.defect_type}<span style={{ opacity: 0.6, marginLeft: 4 }}>{(defect.confidence*100).toFixed(0)}</span></div>
                </foreignObject>
              )}
            </g>
          );
        })}
      </svg>
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

// ── Right pane with tabs ─────────────────────────────────────────────────
function RightPane({ defect, tab, setTab }){
  return (
    <div style={{
      padding: 18, background: "linear-gradient(180deg, var(--bg-1) 0%, #0a0a10 100%)",
      display: "flex", flexDirection: "column", gap: 12, minHeight: 0,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div>
          <div className="eyebrow">VLM 输出 · {variantModel(defect.variant)} · {variantLabel(defect.variant)}</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 4 }}>
            <span style={{ fontSize: 14, color: "var(--fg)", fontWeight: 500 }}>
              {tab === "json" ? "JSON 流输出" : tab === "metrics" ? "VLM 指标" : "溯源"}
            </span>
            <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>· DefectRead v1</span>
          </div>
        </div>
        <Tabs value={tab} onChange={setTab}
              options={[{v: "json", l: "JSON"}, {v: "metrics", l: "指标"}, {v: "provenance", l: "溯源"}]} />
      </div>

      {tab === "json" && <JsonTab defect={defect} />}
      {tab === "metrics" && <MetricsTab defect={defect} />}
      {tab === "provenance" && <ProvenanceTab defect={defect} />}

      <div style={{
        padding: "8px 12px", border: "1px solid var(--line-soft)",
        borderLeft: `2px solid var(--acc)`, background: "var(--bg-2)",
        fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--fg-2)",
      }}>
        payload 遵循 <span style={{ color: "var(--fg-1)" }}>DefectRead v1</span> · 图像来自 <span style={{ color: "var(--fg-1)" }}>/static/defects/…</span>
      </div>
    </div>
  );
}

function Tabs({ value, onChange, options }){
  return (
    <div style={{ display: "inline-flex", border: "1px solid var(--line)", background: "var(--bg-1)" }}>
      {options.map((o, i) => {
        const active = value === o.v;
        return (
          <button key={o.v} onClick={() => onChange(o.v)}
                  style={{
                    padding: "5px 12px",
                    fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.12em",
                    fontWeight: 600, textTransform: "uppercase",
                    background: active ? "var(--acc)" : "transparent",
                    color: active ? "var(--bg)" : "var(--fg-2)",
                    border: "none",
                    borderRight: i < options.length - 1 ? "1px solid var(--line)" : "none",
                    cursor: "pointer",
                  }}>{o.l}</button>
        );
      })}
    </div>
  );
}

// ── JSON tab ─────────────────────────────────────────────────────────────
function JsonTab({ defect }){
  const json = useStreamingJson(defect);
  const lines = json.text.split("\n");
  return (
    <div style={{
      flex: 1, position: "relative",
      background: "#08080c", border: "1px solid var(--line)",
      padding: "14px 16px",
      fontFamily: "var(--font-mono)", fontSize: 12, lineHeight: 1.7,
      minHeight: 320, overflow: "hidden",
    }}>
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
        }}>vlm_output.json · {variantLabel(defect.variant)}</span>
        <span style={{ flex: 1 }} />
        <span className="mono" style={{ fontSize: 9, color: json.done && defect.vlm_metrics.json_parse_ok ? "var(--ok)" : "var(--warn)" }}>
          {!json.done ? "● 流输出中" : (defect.vlm_metrics.json_parse_ok ? "✓ 已解析" : "✗ 重试")}
        </span>
        <span className="mono" style={{ fontSize: 9, color: "var(--fg-4)", marginLeft: 8 }}>schema v1</span>
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
      if (p >= target.length){ setPos(target.length); clearInterval(id); }
      else setPos(p);
    }, 24);
    return () => clearInterval(id);
  }, [defect.id]);
  return { text: target.slice(0, pos), done: pos >= target.length };
}

function highlightJson(line){
  return line
    .replace(/("(?:[^"\\]|\\.)*"):/g, '<span style="color: #7cdcff;">$1</span>:')
    .replace(/: ("(?:[^"\\]|\\.)*")/g, ': <span style="color: var(--acc);">$1</span>')
    .replace(/: (-?\d+\.?\d*)/g, ': <span style="color: var(--core-1);">$1</span>')
    .replace(/: (true|false|null)/g, ': <span style="color: #ff9f6c;">$1</span>');
}

// ── Metrics tab ──────────────────────────────────────────────────────────
function MetricsTab({ defect }){
  const m = defect.vlm_metrics;
  const items = [
    { k: "ttft_ms",        l: "首字延迟",          v: m.ttft_ms,       u: "ms",   c: variantColor(defect.variant), big: true },
    { k: "decode_tps",     l: "解码速率",        v: m.decode_tps.toFixed(2), u: "tok/s", c: "var(--acc)", big: true },
    { k: "prompt_tokens",  l: "提示词元",    v: m.prompt_tokens, u: "" },
    { k: "output_tokens",  l: "输出词元",    v: m.output_tokens, u: "" },
    { k: "rss_mb",         l: "VLM 内存",       v: m.rss_mb,        u: "MB" },
    { k: "anomaly_score",  l: "异常分数 σ",     v: defect.anomaly_score, u: "", c: "var(--warn)" },
    { k: "confidence",     l: "置信度",    v: (defect.confidence*100).toFixed(1), u: "%" },
    { k: "json_parse_ok",  l: "JSON 解析",    v: m.json_parse_ok ? "OK" : "FAIL",
      u: "", c: m.json_parse_ok ? "var(--ok)" : "var(--crit)" },
  ];
  return (
    <div style={{
      flex: 1, background: "var(--bg-1)", border: "1px solid var(--line)",
      display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, padding: 0,
      backgroundColor: "var(--line)", minHeight: 320,
    }}>
      {items.map(it => (
        <div key={it.k} style={{
          background: "var(--bg-1)", padding: "14px 16px",
        }}>
          <div className="eyebrow" style={{ fontSize: 9 }}>{it.l}</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginTop: 6 }}>
            <span className="mono" style={{
              fontSize: it.big ? 26 : 18, fontWeight: 500,
              color: it.c || "var(--fg)",
              letterSpacing: "-0.01em", fontVariantNumeric: "tabular-nums",
            }}>{it.v}</span>
            {it.u && <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>{it.u}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Provenance tab ───────────────────────────────────────────────────────
function ProvenanceTab({ defect }){
  const rows = [
    ["ID",             `#${defect.id}`],
    ["生产线",          defect.line_id],
    ["类别",       defect.category],
    ["缺陷类型",       defect.defect_type],
    ["变体",             defect.variant],
    ["边缘时间戳",     fmtDateTime(defect.edge_ts)],
    ["服务器时间戳",  fmtDateTime(defect.server_ts)],
    ["上传延迟",        `${defect.server_ts - defect.edge_ts} ms`],
    ["图像路径",        defect.image_url],
    ["版本",             defect.schema_version],
    ["追踪事件",        `${defect.trace_events?.length ?? 0} 条 · Chrome trace`],
  ];
  return (
    <div style={{
      flex: 1, background: "var(--bg-1)", border: "1px solid var(--line)",
      padding: "12px 0", minHeight: 320, overflow: "auto",
    }}>
      {rows.map(([k, v]) => (
        <div key={k} style={{
          display: "grid", gridTemplateColumns: "140px 1fr",
          padding: "7px 16px",
          borderBottom: "1px solid var(--line-soft)",
        }}>
          <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>{k}</span>
          <span className="mono" style={{
            fontSize: 11, color: "var(--fg-1)", wordBreak: "break-all",
            letterSpacing: 0,
          }}>{v}</span>
        </div>
      ))}
    </div>
  );
}

// ── Sample placeholders (15 categories) ──────────────────────────────────
function SimulatedSample({ category }){
  // Map every category to a stylized SVG placeholder. Use abstract shapes.
  const C = {
    bottle:     <BottleSample />,
    cable:      <CableSample />,
    capsule:    <CapsuleSample />,
    carpet:     <SurfaceSample tint="#5b3a2a" pattern="weave" />,
    grid:       <SurfaceSample tint="#3a3a3f" pattern="grid" />,
    hazelnut:   <BlobSample tint="#7a5536" />,
    leather:    <SurfaceSample tint="#3d2218" pattern="leather" />,
    metal_nut:  <NutSample />,
    pill:       <PillSample />,
    screw:      <ScrewSample />,
    tile:       <SurfaceSample tint="#4a4a55" pattern="tile" />,
    toothbrush: <ToothbrushSample />,
    transistor: <TransistorSample />,
    wood:       <SurfaceSample tint="#5a3d22" pattern="wood" />,
    zipper:     <ZipperSample />,
  };
  return C[category] || <NutSample />;
}

const _bg = "#0a0a10";

function NutSample(){
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <rect width="200" height="150" fill={_bg} />
      <polygon points="100,40 140,60 140,100 100,120 60,100 60,60" fill="#252530" stroke="#3a3a45" />
      <circle cx="100" cy="80" r="14" fill="#0a0a10" stroke="#3a3a45" />
    </svg>
  );
}
function ScrewSample(){
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <rect width="200" height="150" fill={_bg} />
      <ellipse cx="100" cy="40" rx="22" ry="6" fill="#2a2a35" stroke="#4a4a5a" strokeWidth="0.5" />
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
      <rect width="200" height="150" fill={_bg} />
      <rect x="55" y="65" width="90" height="28" rx="14" fill="#4a4a55" stroke="#5a5a6a" />
      <line x1="100" y1="65" x2="100" y2="93" stroke="#1a1a25" />
    </svg>
  );
}
function BottleSample(){
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <rect width="200" height="150" fill={_bg} />
      <circle cx="100" cy="80" r="48" fill="#1a2c3a" stroke="#2a4a5a" />
      <circle cx="100" cy="80" r="32" fill="#0a1a25" stroke="#1a3a4a" />
    </svg>
  );
}
function CapsuleSample(){
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <rect width="200" height="150" fill={_bg} />
      <rect x="50" y="62" width="100" height="34" rx="17" fill="#5a4a3a" stroke="#6a5a4a" />
      <rect x="50" y="62" width="50" height="34" rx="17" fill="#3a2a1a" />
    </svg>
  );
}
function CableSample(){
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <rect width="200" height="150" fill={_bg} />
      <circle cx="100" cy="75" r="42" fill="none" stroke="#3a3a45" strokeWidth="14" />
      <circle cx="100" cy="75" r="42" fill="none" stroke="#5a5a65" strokeWidth="2" strokeDasharray="4 6" />
    </svg>
  );
}
function ToothbrushSample(){
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <rect width="200" height="150" fill={_bg} />
      <rect x="60" y="68" width="80" height="14" fill="#2a2a35" />
      {Array.from({length: 24}).map((_, i) => (
        <line key={i} x1={62 + i*3.3} y1="56" x2={62 + i*3.3} y2="68" stroke="#5a5a6a" strokeWidth="0.6" />
      ))}
    </svg>
  );
}
function TransistorSample(){
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <rect width="200" height="150" fill={_bg} />
      <rect x="70" y="55" width="60" height="48" fill="#1a1a25" stroke="#3a3a48" />
      <line x1="80" y1="103" x2="80" y2="120" stroke="#6a6a75" />
      <line x1="100" y1="103" x2="100" y2="120" stroke="#6a6a75" />
      <line x1="120" y1="103" x2="120" y2="120" stroke="#6a6a75" />
    </svg>
  );
}
function ZipperSample(){
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <rect width="200" height="150" fill={_bg} />
      {Array.from({length: 18}).map((_, i) => (
        <g key={i}>
          <rect x="80" y={20 + i*7} width="14" height="3" fill="#5a5a6a" />
          <rect x="106" y={23 + i*7} width="14" height="3" fill="#5a5a6a" />
        </g>
      ))}
    </svg>
  );
}
function BlobSample({ tint = "#7a5536" }){
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <rect width="200" height="150" fill={_bg} />
      <ellipse cx="100" cy="75" rx="42" ry="36" fill={tint} stroke="#4a3a2a" />
    </svg>
  );
}
function SurfaceSample({ tint = "#3a3a45", pattern = "grid" }){
  return (
    <svg viewBox="0 0 200 150" preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <rect width="200" height="150" fill={tint} />
      {pattern === "grid" && Array.from({length: 20}).map((_, i) => (
        <g key={i}>
          <line x1={i*10} y1="0" x2={i*10} y2="150" stroke="#000" strokeOpacity="0.25" />
          <line x1="0" y1={i*10} x2="200" y2={i*10} stroke="#000" strokeOpacity="0.25" />
        </g>
      ))}
      {pattern === "weave" && Array.from({length: 16}).map((_, i) => (
        <line key={i} x1="0" y1={i*10 + 4} x2="200" y2={i*10 + 4} stroke="#000" strokeOpacity="0.35" strokeWidth="2" />
      ))}
      {pattern === "wood" && Array.from({length: 12}).map((_, i) => (
        <path key={i} d={`M0,${i*13} Q100,${i*13 + 4} 200,${i*13}`} fill="none" stroke="#000" strokeOpacity="0.3" strokeWidth="1.5" />
      ))}
      {pattern === "leather" && Array.from({length: 40}).map((_, i) => (
        <circle key={i} cx={(i * 17) % 200} cy={((i * 23) % 150)} r="2" fill="#000" fillOpacity="0.3" />
      ))}
      {pattern === "tile" && (
        <>
          <line x1="100" y1="0" x2="100" y2="150" stroke="#000" strokeOpacity="0.4" strokeWidth="2" />
          <line x1="0" y1="75" x2="200" y2="75" stroke="#000" strokeOpacity="0.4" strokeWidth="2" />
        </>
      )}
    </svg>
  );
}

// ── Pills ────────────────────────────────────────────────────────────────
function SevPill({ value }){
  const c = { low: "var(--ok)", medium: "var(--warn)", high: "var(--crit)" }[value];
  const l = { low: "LOW", medium: "MED", high: "HIGH" }[value];
  return <span className="mono" style={{
    fontSize: 9, padding: "2px 7px", border: `1px solid ${c}`, color: c,
    letterSpacing: "0.12em", fontWeight: 700,
    background: `color-mix(in srgb, ${c} 14%, transparent)`,
  }}>{l}</span>;
}
function CatPill({ value }){
  const label = (window.CATEGORY_LABEL && window.CATEGORY_LABEL[value]) || value;
  return <span className="mono" style={{
    fontSize: 9, padding: "2px 7px", border: "1px solid var(--line-hot)",
    color: "var(--fg-2)", letterSpacing: "0.08em", fontWeight: 600, textTransform: "uppercase",
    background: "var(--bg-2)",
  }}>{label}</span>;
}
function VariantPill({ value, compact }){
  const v = normalizeVariant(value);
  const c = variantColor(v);
  const label = variantLabel(v);
  return <span className="mono" style={{
    fontSize: 9, padding: "2px 7px", border: `1px solid ${c}`, color: c,
    letterSpacing: "0.06em", fontWeight: 700,
    background: `color-mix(in srgb, ${c} 12%, transparent)`,
  }}>{compact ? v : label}</span>;
}

Object.assign(window, { FrameInspector, FrameCanvas, SevPill, CatPill, VariantPill, SimulatedSample });
