// V2 AB Comparison — emphasizes LoRA wins (the engineering decision).
const { useState: _abS, useEffect: _abE } = React;

function ABCompare({ stats, focus = "ttft" }){
  const A = stats.ab_compare.A;
  const B = stats.ab_compare.B;
  const metrics = [
    { id: "ttft",  label: "First-Token Latency", a: A.avg_ttft_ms, b: B.avg_ttft_ms, unit: "ms",   hi: "low",  digits: 0, max: 2800 },
    { id: "json",  label: "JSON Parse OK",       a: A.json_ok_rate * 100, b: B.json_ok_rate * 100, unit: "%", hi: "high", digits: 1, max: 100 },
    { id: "tps",   label: "Decode Throughput",   a: A.avg_decode_tps, b: B.avg_decode_tps, unit: "tok/s", hi: "high", digits: 2, max: 14 },
    { id: "rss",   label: "Runtime RSS",         a: A.avg_rss_mb, b: B.avg_rss_mb, unit: "MB",  hi: "low",  digits: 0, max: 3500 },
    { id: "ptok",  label: "Prompt Tokens",       a: 1140, b: 78, unit: "tok", hi: "low", digits: 0, max: 1500 },
  ];
  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", borderBottom: "1px solid var(--line)" }}>
        <ABHeader side="A" color="var(--sig-violet)"
                  title="BASE + LONG PROMPT"
                  sub="Qwen3-VL-2B · few-shot + JSON schema · ~1140 tok"
                  count={A.count} />
        <ABHeader side="B" color="var(--sig-teal)"
                  title="LoRA r16 + MINIMAL PROMPT"
                  sub="MVTec AD finetune · prompt ≤ 100 tok"
                  count={B.count} winner />
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "var(--font-sans)" }}>
        <thead>
          <tr style={{ background: "var(--bg-2)", height: 32 }}>
            <th style={thS}>METRIC</th>
            <th style={{ ...thS, textAlign: "right", color: "var(--sig-violet)" }}>A</th>
            <th style={thS}></th>
            <th style={{ ...thS, textAlign: "right", color: "var(--sig-teal)" }}>B</th>
            <th style={{ ...thS, textAlign: "right" }}>Δ B vs A</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map(m => {
            const delta = m.b - m.a;
            const pct = m.a !== 0 ? (delta / m.a) * 100 : 0;
            const better = m.hi === "high" ? delta > 0 : delta < 0;
            const pa = Math.min(1, m.a / m.max);
            const pb = Math.min(1, m.b / m.max);
            const winnerCol = m.id === focus ? "var(--bg-3)" : "transparent";
            return (
              <tr key={m.id} style={{ background: winnerCol, borderBottom: "1px solid var(--line-soft)", height: 50 }}>
                <td style={tdS}>
                  <div style={{ fontSize: 12, color: "var(--fg)", fontWeight: 500 }}>{m.label}</div>
                  <div className="mono" style={{ fontSize: 9, color: "var(--fg-3)", marginTop: 2 }}>
                    {m.hi === "low" ? "↓ lower is better" : "↑ higher is better"}
                  </div>
                </td>
                <td style={{ ...tdS, textAlign: "right", width: "26%" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "flex-end" }}>
                    <div style={{ flex: 1, height: 4, background: "var(--bg-3)", maxWidth: 100 }}>
                      <div style={{ width: `${pa*100}%`, height: "100%", background: "var(--sig-violet)" }} />
                    </div>
                    <span className="mono" style={{ fontSize: 14, color: "var(--fg-1)", fontVariantNumeric: "tabular-nums", minWidth: 60 }}>
                      {fmtNumber(m.a, { digits: m.digits })}
                    </span>
                  </div>
                </td>
                <td style={{ ...tdS, textAlign: "center", width: 24, color: "var(--fg-3)" }}>vs</td>
                <td style={{ ...tdS, textAlign: "right", width: "26%" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "flex-end" }}>
                    <div style={{ flex: 1, height: 4, background: "var(--bg-3)", maxWidth: 100 }}>
                      <div style={{ width: `${pb*100}%`, height: "100%", background: "var(--sig-teal)" }} />
                    </div>
                    <span className="mono" style={{ fontSize: 16, color: "var(--fg)", fontVariantNumeric: "tabular-nums", fontWeight: 600, minWidth: 60 }}>
                      {fmtNumber(m.b, { digits: m.digits })}
                    </span>
                  </div>
                </td>
                <td style={{ ...tdS, textAlign: "right", width: 130 }}>
                  <span className="mono" style={{
                    display: "inline-block", padding: "2px 8px",
                    border: `1px solid ${better ? "var(--sig-green)" : "var(--sig-red)"}`,
                    color: better ? "var(--sig-green)" : "var(--sig-red)",
                    background: `color-mix(in srgb, ${better ? "var(--sig-green)" : "var(--sig-red)"} 12%, transparent)`,
                    fontSize: 11, fontWeight: 600,
                  }}>
                    {delta > 0 ? "+" : ""}{Math.abs(pct) < 1000 ? pct.toFixed(1) : Math.round(pct)}%
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div style={{
        padding: "10px 14px", background: "var(--bg-2)", borderTop: "1px solid var(--line)",
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>
          eval n=<span style={{ color: "var(--fg-1)" }}>{A.count + B.count}</span> · stratified 70/30 split · MVTec test set
        </span>
        <span className="mono" style={{ fontSize: 10, color: "var(--sig-teal)" }}>
          → DECISION: ship variant B for production
        </span>
      </div>
    </div>
  );
}

const thS = { fontFamily: "var(--font-mono)", fontSize: 9, fontWeight: 500, letterSpacing: "0.16em", color: "var(--fg-3)", padding: "0 14px", borderBottom: "1px solid var(--line)", textAlign: "left" };
const tdS = { padding: "10px 14px", verticalAlign: "middle" };

function ABHeader({ side, title, sub, color, count, winner }){
  return (
    <div style={{ padding: "14px 18px", borderRight: "1px solid var(--line)", position: "relative" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{
          width: 28, height: 28, border: `1px solid ${color}`, color,
          display: "inline-flex", alignItems: "center", justifyContent: "center",
          fontFamily: "var(--font-mono)", fontSize: 14, fontWeight: 700,
          background: `color-mix(in srgb, ${color} 14%, transparent)`,
        }}>{side}</span>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--fg)" }}>{title}</div>
          <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginTop: 2 }}>{sub}</div>
        </div>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 10, gap: 12 }}>
        <span className="mono" style={{ fontSize: 9, color: "var(--fg-3)" }}>n = {count}</span>
        {winner && (
          <span className="mono" style={{
            fontSize: 9, padding: "1px 6px", border: `1px solid ${color}`, color,
            background: `color-mix(in srgb, ${color} 12%, transparent)`,
            fontWeight: 600, letterSpacing: "0.14em",
          }}>★ WINNER · 4 of 5 axes</span>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { ABCompare });
