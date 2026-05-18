// V4 Recent Stream — detection feed with category/variant filters.
// Selected card opens DetailDrawer (rendered separately in overview).

const { useState: _vs4S, useMemo: _vs4M } = React;

function RecentStream({ defects, onSelect, selectedId }){
  const [sev,  setSev]  = _vs4S("all");
  const [cat,  setCat]  = _vs4S("all");
  const [vr,   setVr]   = _vs4S("all");

  const filtered = _vs4M(() => {
    return defects.filter(d => {
      if (sev !== "all" && d.severity !== sev) return false;
      if (cat !== "all" && d.category !== cat) return false;
      if (vr  !== "all" && normalizeVariant(d.variant) !== vr) return false;
      return true;
    });
  }, [defects, sev, cat, vr]);

  const shown = filtered.slice(0, 12);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end",
                    marginBottom: 18, gap: 16, flexWrap: "wrap" }}>
        <div>
          <div className="eyebrow">最近检测</div>
          <h2 style={{ margin: 0, marginTop: 6, fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em" }}>
            最近 <span className="mono" style={{ color: "var(--acc)" }}>{shown.length}</span>
            <span style={{ color: "var(--fg-3)", fontWeight: 400 }}> / {filtered.length} 帧</span>
          </h2>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <SegFilter value={sev} onChange={setSev}
                     options={[["all","全部"],["high","高"],["medium","中"],["low","低"]]} />
          <FilterSelect label="类别" value={cat} onChange={setCat}
                        options={[["all","全部 15 类"], ...MVTEC_CATEGORIES.map(c => [c, CATEGORY_LABEL[c]])]} />
          <FilterSelect label="变体" value={vr} onChange={setVr}
                        options={[["all","全部变体"], ...VARIANTS.map(v => [v, VARIANT_LABEL[v]])]} />
        </div>
      </div>

      <div style={{
        display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
        gap: 1, background: "var(--line)", border: "1px solid var(--line)",
      }}>
        {shown.map(d => (
          <DetectionCard key={d.id} defect={d}
                         selected={d.id === selectedId}
                         onClick={() => onSelect && onSelect(d)} />
        ))}
        {!shown.length && (
          <div style={{ background: "var(--bg-1)", padding: 40, textAlign: "center", color: "var(--fg-3)" }}>
            <span className="mono" style={{ fontSize: 12 }}>没有符合条件的帧。</span>
          </div>
        )}
      </div>
    </div>
  );
}

function SegFilter({ value, onChange, options }){
  return (
    <div style={{ display: "inline-flex", border: "1px solid var(--line)" }}>
      {options.map(([v, l], i) => {
        const active = value === v;
        return (
          <button key={v} onClick={() => onChange(v)} style={{
            padding: "5px 11px",
            fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.1em",
            fontWeight: 600, textTransform: "uppercase",
            background: active ? "var(--acc)" : "transparent",
            color: active ? "var(--bg)" : "var(--fg-2)",
            border: "none",
            borderRight: i < options.length - 1 ? "1px solid var(--line)" : "none",
            cursor: "pointer",
          }}>{l}</button>
        );
      })}
    </div>
  );
}

function FilterSelect({ label, value, onChange, options }){
  return (
    <label style={{ display: "inline-flex", alignItems: "center", gap: 6,
                    border: "1px solid var(--line)", padding: "3px 6px 3px 10px",
                    background: "var(--bg-1)" }}>
      <span className="eyebrow" style={{ fontSize: 9 }}>{label}</span>
      <select value={value} onChange={e => onChange(e.target.value)}
              style={{
                fontFamily: "var(--font-mono)", fontSize: 11,
                background: "transparent", color: "var(--fg-1)",
                border: "none", outline: "none", padding: "3px 6px",
                cursor: "pointer",
              }}>
        {options.map(([v, l]) => (
          <option key={v} value={v} style={{ background: "var(--bg)", color: "var(--fg)" }}>{l}</option>
        ))}
      </select>
    </label>
  );
}

function DetectionCard({ defect, selected, onClick }){
  const total = Math.round(defect.pipeline_ms.efficientad + defect.pipeline_ms.fastsam + defect.pipeline_ms.qwen3vl);
  const sevColor = { low: "var(--ok)", medium: "var(--warn)", high: "var(--crit)" }[defect.severity];

  return (
    <button onClick={onClick}
      style={{
        background: selected ? "var(--bg-2)" : "var(--bg-1)",
        border: "none",
        borderLeft: selected ? "3px solid var(--acc)" : "3px solid transparent",
        padding: 14, textAlign: "left", cursor: "pointer",
        display: "flex", flexDirection: "column", gap: 10,
        transition: "background 0.12s",
        position: "relative",
      }}
      onMouseEnter={e => { if (!selected) e.currentTarget.style.background = "var(--bg-2)"; }}
      onMouseLeave={e => { if (!selected) e.currentTarget.style.background = "var(--bg-1)"; }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span className="mono" style={{ fontSize: 11, color: "var(--fg-2)" }}>#{defect.id}</span>
        <span style={{ display: "flex", gap: 4 }}>
          <SevPill value={defect.severity} />
          <VariantPill value={defect.variant} compact />
        </span>
      </div>

      <div style={{ position: "relative", width: "100%", aspectRatio: "16/10", background: "var(--bg)", border: "1px solid var(--line)", overflow: "hidden" }}>
        <SimulatedSample category={defect.category} />
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
          {defect.bboxes.slice(0, 2).map((b, i) => (
            <rect key={i} x={b.x*100} y={b.y*100} width={b.w*100} height={b.h*100}
                  fill="none" stroke={sevColor} strokeWidth="0.3" vectorEffect="non-scaling-stroke" />
          ))}
        </svg>
        <div style={{
          position: "absolute", top: 4, left: 6,
          fontFamily: "var(--font-mono)", fontSize: 8, color: "var(--fg-3)",
        }}>{defect.line_id} · {CATEGORY_LABEL[defect.category]}</div>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={{ fontSize: 13, color: "var(--fg)", fontWeight: 500 }}>{defect.defect_type.replace(/_/g, " ")}</span>
        <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>{(defect.confidence*100).toFixed(0)}%</span>
      </div>

      <div style={{ display: "flex", height: 4, background: "var(--bg-3)" }}>
        <div style={{ width: `${(defect.pipeline_ms.efficientad / total) * 100}%`, background: "var(--core-0)" }} />
        <div style={{ width: `${(defect.pipeline_ms.fastsam / total) * 100}%`, background: "var(--core-1)" }} />
        <div style={{ width: `${(defect.pipeline_ms.qwen3vl / total) * 100}%`, background: "var(--core-2)" }} />
      </div>

      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>{fmtTime(defect.edge_ts)}</span>
        <span className="mono" style={{ fontSize: 10, color: total > 2400 ? "var(--warn)" : "var(--fg-2)" }}>
          Σ {total}ms
        </span>
      </div>
    </button>
  );
}

// ── DetailDrawer ─────────────────────────────────────────────────────────
function DetailDrawer({ defect, onClose, onOpenProfile }){
  const [tab, setTab] = _vs4S("json");
  // close on Escape
  React.useEffect(() => {
    if (!defect) return;
    const onKey = e => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [defect, onClose]);

  if (!defect) return null;
  const m = defect.vlm_metrics;
  const total = Math.round(defect.pipeline_ms.efficientad + defect.pipeline_ms.fastsam + defect.pipeline_ms.qwen3vl);

  return (
    <aside style={{
      position: "fixed", top: 0, right: 0, bottom: 0,
      width: 460, maxWidth: "100vw",
      background: "var(--bg-1)",
      borderLeft: "1px solid var(--line-hot)",
      boxShadow: "-1px 0 24px rgba(0,0,0,0.5)",
      display: "flex", flexDirection: "column",
      animation: "slide-in-right 0.18s ease-out both",
      zIndex: 50, overflow: "hidden",
    }}>
      <style>{`
        @keyframes slide-in-right { from { transform: translateX(20px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
      `}</style>

      {/* Header */}
      <div style={{
        padding: "14px 18px",
        borderBottom: "1px solid var(--line)",
        background: "var(--bg-2)",
        display: "flex", justifyContent: "space-between", alignItems: "flex-start",
      }}>
        <div>
          <div className="eyebrow">缺陷详情 · {defect.line_id}</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 4 }}>
            <span className="mono" style={{ fontSize: 18, color: "var(--fg)", fontWeight: 600 }}>#{defect.id}</span>
            <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>· {fmtTime(defect.edge_ts)}</span>
          </div>
          <div style={{ display: "flex", gap: 5, marginTop: 8, flexWrap: "wrap" }}>
            <SevPill value={defect.severity} />
            <CatPill value={defect.category} />
            <VariantPill value={defect.variant} compact />
          </div>
        </div>
        <button onClick={onClose} style={{
          background: "transparent", border: "1px solid var(--line)",
          color: "var(--fg-2)", padding: "4px 10px",
          fontFamily: "var(--font-mono)", fontSize: 11, cursor: "pointer",
        }}>ESC ✕</button>
      </div>

      {/* Scrollable body */}
      <div style={{ flex: 1, overflowY: "auto", padding: 18, display: "flex", flexDirection: "column", gap: 16 }}>
        {/* Frame */}
        <div>
          <div className="eyebrow" style={{ marginBottom: 8 }}>帧 · {defect.defect_type.replace(/_/g, " ")}</div>
          <FrameCanvas defect={defect} aspect="16/10" />
        </div>

        {/* Pipeline gantt */}
        <div>
          <div className="eyebrow" style={{ marginBottom: 8 }}>流水线 · {total} ms</div>
          <FrameGanttMini defect={defect} />
        </div>

        {/* Metrics grid */}
        <div>
          <div className="eyebrow" style={{ marginBottom: 8 }}>VLM 指标 · {variantLabel(defect.variant)}</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "var(--line)", border: "1px solid var(--line)" }}>
            <DMetric label="首字延迟" v={m.ttft_ms} u="ms" c={variantColor(defect.variant)} />
            <DMetric label="解码速率" v={m.decode_tps.toFixed(2)} u="tok/s" c="var(--acc)" />
            <DMetric label="提示词元" v={m.prompt_tokens} />
            <DMetric label="输出词元" v={m.output_tokens} />
            <DMetric label="内存" v={m.rss_mb} u="MB" />
            <DMetric label="JSON 解析" v={m.json_parse_ok ? "OK" : "FAIL"}
                     c={m.json_parse_ok ? "var(--ok)" : "var(--crit)"} />
          </div>
        </div>

        {/* JSON block */}
        <div>
          <div className="eyebrow" style={{ marginBottom: 8 }}>JSON</div>
          <pre style={{
            margin: 0, padding: "12px 14px", background: "#08080c",
            border: "1px solid var(--line)",
            fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--fg-1)",
            lineHeight: 1.6, whiteSpace: "pre-wrap", wordBreak: "break-word",
            maxHeight: 220, overflow: "auto",
          }}
          dangerouslySetInnerHTML={{ __html: JSON.stringify({
            category: defect.category,
            defect_type: defect.defect_type,
            severity: defect.severity,
            confidence: defect.confidence,
            bboxes: defect.bboxes,
            description: defect.description,
          }, null, 2).split("\n").map(l => highlightJsonLine(l)).join("\n") }} />
        </div>

        {/* Provenance */}
        <div>
          <div className="eyebrow" style={{ marginBottom: 8 }}>溯源</div>
          <div style={{ border: "1px solid var(--line)", padding: "4px 0" }}>
            {[
              ["边缘时间戳",   fmtDateTime(defect.edge_ts)],
              ["服务器时间戳", fmtDateTime(defect.server_ts)],
              ["图像路径", defect.image_url],
              ["版本",    defect.schema_version],
            ].map(([k, v]) => (
              <div key={k} style={{
                display: "grid", gridTemplateColumns: "100px 1fr",
                padding: "5px 12px",
              }}>
                <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>{k}</span>
                <span className="mono" style={{ fontSize: 10, color: "var(--fg-1)", wordBreak: "break-all" }}>{v}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{
        borderTop: "1px solid var(--line)", padding: "12px 18px",
        background: "var(--bg-2)", display: "flex", justifyContent: "space-between", gap: 8,
      }}>
        <button onClick={() => onOpenProfile && onOpenProfile(defect)} style={{
          background: "var(--acc)", color: "var(--bg)", border: "none",
          padding: "8px 14px", fontFamily: "var(--font-mono)", fontSize: 11,
          letterSpacing: "0.1em", fontWeight: 700, textTransform: "uppercase",
          cursor: "pointer",
        }}>在性能剖析中打开 →</button>
        <button onClick={onClose} style={{
          background: "transparent", border: "1px solid var(--line)",
          color: "var(--fg-2)", padding: "8px 14px",
          fontFamily: "var(--font-mono)", fontSize: 11,
          letterSpacing: "0.1em", fontWeight: 600, textTransform: "uppercase",
          cursor: "pointer",
        }}>关闭</button>
      </div>
    </aside>
  );
}

function DMetric({ label, v, u, c = "var(--fg)" }){
  return (
    <div style={{ background: "var(--bg-1)", padding: "12px 14px" }}>
      <div className="eyebrow" style={{ fontSize: 9 }}>{label}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 3, marginTop: 5 }}>
        <span className="mono" style={{ fontSize: 18, fontWeight: 500, color: c, letterSpacing: "-0.01em" }}>{v}</span>
        {u && <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>{u}</span>}
      </div>
    </div>
  );
}

function FrameGanttMini({ defect }){
  const stages = [
    { color: "var(--core-0)", ms: defect.pipeline_ms.efficientad, label: "EfficientAD" },
    { color: "var(--core-1)", ms: defect.pipeline_ms.fastsam,     label: "FastSAM" },
    { color: "var(--core-2)", ms: defect.pipeline_ms.qwen3vl,     label: "Qwen3-VL" },
  ];
  const total = stages.reduce((s, x) => s + x.ms, 0);
  return (
    <div>
      <div style={{ display: "flex", height: 10, border: "1px solid var(--line)", background: "var(--bg-3)" }}>
        {stages.map((s, i) => (
          <div key={i} style={{ width: `${(s.ms / total) * 100}%`, background: s.color }} />
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", marginTop: 8, gap: 8 }}>
        {stages.map((s, i) => (
          <div key={i} style={{ display: "flex", alignItems: "baseline", gap: 5 }}>
            <span style={{ width: 6, height: 6, background: s.color }} />
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

function highlightJsonLine(line){
  return line
    .replace(/("(?:[^"\\]|\\.)*"):/g, '<span style="color: #7cdcff;">$1</span>:')
    .replace(/: ("(?:[^"\\]|\\.)*")/g, ': <span style="color: var(--acc);">$1</span>')
    .replace(/: (-?\d+\.?\d*)/g, ': <span style="color: var(--core-1);">$1</span>')
    .replace(/: (true|false|null)/g, ': <span style="color: #ff9f6c;">$1</span>');
}

Object.assign(window, { RecentStream, DetailDrawer });
