// V3 Stream — visual cards, not a table.
const { useState: _vs3S, useMemo: _vs3M } = React;

function RecentStream({ defects, onSelect, selectedId }){
  const [filter, setFilter] = _vs3S("all");
  const filtered = _vs3M(() => {
    if (filter === "all") return defects;
    if (filter === "high") return defects.filter(d => d.severity === "high");
    if (filter === "B") return defects.filter(d => d.variant === "B");
    if (filter === "A") return defects.filter(d => d.variant === "A");
    return defects;
  }, [defects, filter]);

  const shown = filtered.slice(0, 12);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 18 }}>
        <div>
          <div className="eyebrow">RECENT DETECTIONS</div>
          <h2 style={{ margin: 0, marginTop: 6, fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em" }}>
            Last <span className="mono" style={{ color: "var(--acc)" }}>{shown.length}</span> frames
          </h2>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          {[
            ["all",  "All"],
            ["high", "High severity"],
            ["A",    "Variant A"],
            ["B",    "Variant B"],
          ].map(([v, l]) => (
            <button key={v} onClick={() => setFilter(v)} style={{
              background: filter === v ? "var(--acc)" : "transparent",
              color: filter === v ? "var(--bg)" : "var(--fg-2)",
              border: `1px solid ${filter === v ? "var(--acc)" : "var(--line)"}`,
              padding: "5px 12px", fontSize: 12, fontWeight: 500,
              fontFamily: "var(--font-sans)", letterSpacing: "0",
            }}>{l}</button>
          ))}
        </div>
      </div>

      <div style={{
        display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
        gap: 1, background: "var(--line)",
        border: "1px solid var(--line)",
      }}>
        {shown.map(d => (
          <DetectionCard key={d.id} defect={d}
                         selected={d.id === selectedId}
                         onClick={() => onSelect && onSelect(d)} />
        ))}
      </div>
    </div>
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
        borderLeft: selected ? `3px solid var(--acc)` : "3px solid transparent",
        padding: 14, textAlign: "left", cursor: "pointer",
        display: "flex", flexDirection: "column", gap: 10,
        transition: "background 0.12s",
      }}
      onMouseEnter={e => { if (!selected) e.currentTarget.style.background = "var(--bg-2)"; }}
      onMouseLeave={e => { if (!selected) e.currentTarget.style.background = "var(--bg-1)"; }}
    >
      {/* header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span className="mono" style={{ fontSize: 11, color: "var(--fg-2)" }}>#{defect.id}</span>
        <span style={{ display: "flex", gap: 4 }}>
          <SevPill value={defect.severity} />
          <VarPill value={defect.variant} />
        </span>
      </div>

      {/* mini frame */}
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
        }}>{defect.line_id}</div>
      </div>

      {/* defect type */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={{ fontSize: 13, color: "var(--fg)", fontWeight: 500 }}>{defect.defect_type}</span>
        <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>{(defect.confidence*100).toFixed(0)}%</span>
      </div>

      {/* mini gantt */}
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

Object.assign(window, { RecentStream });
