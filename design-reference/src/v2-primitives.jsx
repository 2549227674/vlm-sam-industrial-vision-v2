// V2 primitives — Profiler / Mission Control aesthetic.
const { useState: _v2State, useEffect: _v2Eff, useMemo: _v2Memo, useRef: _v2Ref } = React;

function Panel({ id, eyebrow, title, right, footer, children, padded = true, hot, style, dataLabel }){
  return (
    <section data-screen-label={dataLabel}
      style={{
        background: "var(--bg-1)",
        border: "1px solid var(--line)",
        borderTop: hot ? `1px solid ${hot}` : "1px solid var(--line)",
        display: "flex", flexDirection: "column",
        ...style,
      }}>
      {(eyebrow || title || right) && (
        <header style={{
          padding: "9px 14px",
          borderBottom: "1px solid var(--line)",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          gap: 10, minHeight: 40, background: "var(--bg-2)",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
            {id && <span className="mono" style={{ color: "var(--sig-cyan)", fontSize: 10, fontWeight: 600 }}>{id}</span>}
            {id && <span style={{ width: 1, height: 14, background: "var(--line)" }} />}
            {eyebrow && <span className="eyebrow">{eyebrow}</span>}
            {title && <span style={{ fontSize: 13, fontWeight: 600, color: "var(--fg)" }}>{title}</span>}
          </div>
          {right && <div style={{ display: "flex", alignItems: "center", gap: 8 }}>{right}</div>}
        </header>
      )}
      <div style={{ padding: padded ? 16 : 0, flex: 1 }}>{children}</div>
      {footer && (
        <footer style={{
          padding: "8px 14px", borderTop: "1px solid var(--line)",
          background: "var(--bg-2)", fontFamily: "var(--font-mono)", fontSize: 10,
          color: "var(--fg-3)", display: "flex", justifyContent: "space-between",
        }}>{footer}</footer>
      )}
    </section>
  );
}

function MetricCell({ label, value, unit, sub, tone = "default", flashKey }){
  const [flash, setFlash] = _v2State(false);
  _v2Eff(() => {
    if (flashKey == null) return;
    setFlash(true);
    const t = setTimeout(() => setFlash(false), 600);
    return () => clearTimeout(t);
  }, [flashKey]);
  const colorMap = {
    default: "var(--fg)",
    cyan:    "var(--sig-cyan)",
    green:   "var(--sig-green)",
    amber:   "var(--sig-amber)",
    red:     "var(--sig-red)",
    violet:  "var(--sig-violet)",
    teal:    "var(--sig-teal)",
  };
  const color = colorMap[tone] ?? "var(--fg)";
  return (
    <div style={{
      padding: "12px 14px",
      borderRight: "1px solid var(--line)",
      position: "relative", overflow: "hidden",
      background: "var(--bg-1)",
      minHeight: 78,
    }}>
      {flash && <span style={{ position: "absolute", inset: 0, background: color, animation: "flash 0.6s forwards", pointerEvents: "none" }} />}
      <div className="eyebrow" style={{ fontSize: 9 }}>{label}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginTop: 6 }}>
        <span className="mono" style={{
          fontSize: 24, fontWeight: 500, color, lineHeight: 1,
          fontVariantNumeric: "tabular-nums", letterSpacing: "-0.01em",
        }}>{value}</span>
        {unit && <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>{unit}</span>}
      </div>
      {sub && <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function StatusDot({ state }){
  const m = {
    online:  { c: "var(--sig-green)", t: "ONLINE",  pulse: true },
    stale:   { c: "var(--sig-amber)", t: "STALE",   pulse: false },
    offline: { c: "var(--sig-red)",   t: "OFFLINE", pulse: false },
  }[state] ?? { c: "var(--sig-green)", t: "ONLINE", pulse: true };
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span style={{ position: "relative", width: 8, height: 8 }}>
        <span style={{
          position: "absolute", inset: 0, background: m.c, borderRadius: "50%",
          animation: m.pulse ? "pulse-dot 1.4s infinite" : "none",
          boxShadow: `0 0 6px ${m.c}`,
        }} />
      </span>
      <span className="mono" style={{ fontSize: 10, color: m.c, letterSpacing: "0.16em", fontWeight: 600 }}>{m.t}</span>
    </span>
  );
}

function SeverityChip({ value, size = "md" }){
  const s = { low: "var(--sev-low)", medium: "var(--sev-med)", high: "var(--sev-high)" }[value];
  const lbl = { low: "LOW", medium: "MED", high: "HIGH" }[value];
  return (
    <span className="mono" style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: size === "sm" ? "0px 5px" : "1px 6px",
      border: `1px solid ${s}`, color: s,
      background: `color-mix(in srgb, ${s} 14%, transparent)`,
      fontSize: size === "sm" ? 9 : 10, letterSpacing: "0.14em", fontWeight: 600,
    }}>
      <span style={{ width: 4, height: 4, background: s, borderRadius: "50%" }} />
      {lbl}
    </span>
  );
}

function CategoryChip({ value }){
  const m = {
    metal_nut: { code: "MN",  c: "var(--sig-cyan)" },
    screw:     { code: "SCR", c: "var(--sig-mag)" },
    pill:      { code: "PIL", c: "var(--sig-amber)" },
  }[value] ?? { code: "—", c: "var(--fg-3)" };
  return (
    <span className="mono" style={{
      fontSize: 9, fontWeight: 600, letterSpacing: "0.08em",
      padding: "1px 5px", border: `1px solid ${m.c}`, color: m.c,
    }}>{m.code}</span>
  );
}

function VariantChip({ value, size = "md" }){
  const c = value === "A" ? "var(--sig-violet)" : "var(--sig-teal)";
  return (
    <span className="mono" style={{
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      width: size === "sm" ? 16 : 20, height: size === "sm" ? 16 : 20,
      border: `1px solid ${c}`, color: c,
      background: `color-mix(in srgb, ${c} 16%, transparent)`,
      fontSize: size === "sm" ? 9 : 10, fontWeight: 700,
    }}>{value}</span>
  );
}

function INT8Badge(){
  return (
    <span className="mono" style={{
      fontSize: 9, fontWeight: 700, color: "var(--sig-cyan)",
      border: "1px solid var(--sig-cyan)", padding: "0 4px", letterSpacing: "0.06em",
    }}>INT8</span>
  );
}

Object.assign(window, { Panel, MetricCell, StatusDot, SeverityChip, CategoryChip, VariantChip, INT8Badge });
