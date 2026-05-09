// V2 Stream — live defect feed with profiler-style row layout.

const { useState: _vsS, useEffect: _vsE, useMemo: _vsM } = React;

function LiveStream({ defects, onSelect, selectedId }){
  const [filter, setFilter] = _vsS({ severity: "all", variant: "all", category: "all" });
  const filtered = _vsM(() => {
    return defects.filter(d => {
      if (filter.severity !== "all" && d.severity !== filter.severity) return false;
      if (filter.variant !== "all" && d.variant !== filter.variant) return false;
      if (filter.category !== "all" && d.category !== filter.category) return false;
      return true;
    });
  }, [defects, filter]);

  const PAGE = 14;
  const rows = filtered.slice(0, PAGE);

  return (
    <div>
      <div style={{
        display: "flex", gap: 14, padding: "10px 14px",
        borderBottom: "1px solid var(--line)", background: "var(--bg-2)",
        alignItems: "center",
      }}>
        <FilterGroup label="SEV" value={filter.severity} onChange={v => setFilter({ ...filter, severity: v })}
                     options={[["all","ALL"],["high","HI"],["medium","MED"],["low","LOW"]]} />
        <FilterGroup label="VAR" value={filter.variant} onChange={v => setFilter({ ...filter, variant: v })}
                     options={[["all","A+B"],["A","A"],["B","B"]]} />
        <FilterGroup label="CAT" value={filter.category} onChange={v => setFilter({ ...filter, category: v })}
                     options={[["all","ALL"],["metal_nut","MN"],["screw","SCR"],["pill","PIL"]]} />
        <span style={{ flex: 1 }} />
        <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>
          shown <span style={{ color: "var(--fg-1)" }}>{rows.length}</span> / {filtered.length}
        </span>
      </div>

      {/* Column header */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "60px 80px 70px 50px 60px 1fr 100px 80px",
        padding: "6px 14px",
        borderBottom: "1px solid var(--line)",
        background: "var(--bg-1)",
        fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--fg-3)",
        letterSpacing: "0.14em", fontWeight: 500,
      }}>
        <span>ID</span>
        <span>TIME</span>
        <span>SEVERITY</span>
        <span>VAR</span>
        <span>CAT</span>
        <span>DEFECT</span>
        <span style={{ textAlign: "right" }}>TOTAL ms</span>
        <span style={{ textAlign: "right" }}>CONF</span>
      </div>

      <div>
        {rows.map((d, i) => {
          const total = Math.round(d.pipeline_ms.efficientad + d.pipeline_ms.fastsam + d.pipeline_ms.qwen3vl);
          const isNew = i === 0 && d._new;
          const isSel = d.id === selectedId;
          return (
            <div key={d.id} onClick={() => onSelect && onSelect(d)}
              style={{
                display: "grid",
                gridTemplateColumns: "60px 80px 70px 50px 60px 1fr 100px 80px",
                padding: "9px 14px",
                borderBottom: "1px solid var(--line-soft)",
                fontSize: 12, alignItems: "center", cursor: "pointer",
                background: isSel ? "color-mix(in srgb, var(--sig-cyan) 8%, var(--bg-1))"
                          : isNew ? "color-mix(in srgb, var(--sig-cyan) 4%, var(--bg-1))"
                          : i % 2 === 0 ? "var(--bg-1)" : "var(--bg-2)",
                borderLeft: isSel ? "2px solid var(--sig-cyan)" : "2px solid transparent",
                position: "relative",
                animation: isNew ? "slide-in-toast 0.4s ease-out" : "none",
              }}
              onMouseEnter={e => { if (!isSel) e.currentTarget.style.background = "var(--bg-3)"; }}
              onMouseLeave={e => { if (!isSel) e.currentTarget.style.background = i % 2 === 0 ? "var(--bg-1)" : "var(--bg-2)"; }}
            >
              <span className="mono" style={{ color: "var(--sig-cyan)", fontSize: 11, fontWeight: 600 }}>#{d.id}</span>
              <span className="mono" style={{ color: "var(--fg-2)", fontSize: 11 }}>{fmtTime(d.edge_ts)}</span>
              <SeverityChip value={d.severity} size="sm" />
              <VariantChip value={d.variant} size="sm" />
              <CategoryChip value={d.category} />
              <span style={{ color: "var(--fg-1)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {d.defect_type}
                <span className="mono" style={{ color: "var(--fg-3)", marginLeft: 6, fontSize: 10 }}>· {d.line_id}</span>
              </span>
              <span className="mono" style={{
                textAlign: "right", color: total > 2400 ? "var(--sig-amber)" : "var(--fg-1)",
                fontVariantNumeric: "tabular-nums", fontSize: 11, fontWeight: 500,
              }}>{total}</span>
              <span className="mono" style={{
                textAlign: "right", color: d.vlm_metrics.json_parse_ok ? "var(--sig-green)" : "var(--sig-red)",
                fontVariantNumeric: "tabular-nums", fontSize: 11,
              }}>
                {(d.confidence * 100).toFixed(1)}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function FilterGroup({ label, value, onChange, options }){
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
      <span className="mono" style={{ fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.14em", marginRight: 4 }}>{label}</span>
      {options.map(([v, l]) => (
        <button key={v} onClick={() => onChange(v)}
          style={{
            background: value === v ? "var(--sig-cyan)" : "transparent",
            color: value === v ? "var(--bg-0)" : "var(--fg-2)",
            border: `1px solid ${value === v ? "var(--sig-cyan)" : "var(--line)"}`,
            padding: "2px 8px", fontFamily: "var(--font-mono)", fontSize: 10,
            fontWeight: value === v ? 700 : 500, letterSpacing: "0.08em", cursor: "pointer",
          }}>{l}</button>
      ))}
    </div>
  );
}

Object.assign(window, { LiveStream });
