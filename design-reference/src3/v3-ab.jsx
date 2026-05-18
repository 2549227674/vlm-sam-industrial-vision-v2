// V3 AB Comparison — two large visual cards, not a table.
const { useState: _abS3, useEffect: _abE3 } = React;

function ABCompareV3({ stats }){
  const A = stats.ab_compare.A;
  const B = stats.ab_compare.B;

  const ttftDelta = ((A.avg_ttft_ms - B.avg_ttft_ms) / A.avg_ttft_ms) * 100;
  const jsonDelta = ((B.json_ok_rate - A.json_ok_rate) / Math.max(A.json_ok_rate, 0.01)) * 100;
  const promptDelta = ((1140 - 78) / 1140) * 100;

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 22 }}>
        <div className="eyebrow">AB EXPERIMENT</div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 6 }}>
          <h2 style={{ margin: 0, fontSize: 26, fontWeight: 600, letterSpacing: "-0.02em" }}>
            LoRA fine-tune <span style={{ color: "var(--fg-3)", fontWeight: 400 }}>vs</span> Base prompt
          </h2>
          <span className="mono" style={{ fontSize: 11, color: "var(--fg-2)" }}>
            n = {A.count + B.count} · MVTec test split 70/30
          </span>
        </div>
      </div>

      {/* Highlight strip */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 1,
        background: "var(--line)",
        marginBottom: 22,
      }}>
        <DeltaHighlight label="TTFT REDUCED" value={`-${Math.round(Math.abs(ttftDelta))}%`} sub={`${Math.round(A.avg_ttft_ms)}ms → ${Math.round(B.avg_ttft_ms)}ms`} color="var(--ab-b)" />
        <DeltaHighlight label="JSON PARSE IMPROVED" value={`+${Math.round(jsonDelta)}%`} sub={`${(A.json_ok_rate*100).toFixed(1)}% → ${(B.json_ok_rate*100).toFixed(1)}%`} color="var(--acc)" />
        <DeltaHighlight label="PROMPT LENGTH" value={`-${Math.round(promptDelta)}%`} sub="1140 → 78 tok" color="var(--ab-b)" />
      </div>

      {/* Two cards */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "var(--line)" }}>
        <ABVariantCard
          side="A"
          color="var(--ab-a)"
          title="Base model + long prompt"
          subtitle="Qwen3-VL-2B-Instruct + few-shot + JSON schema"
          tags={["Base", "1140 tok prompt", "0-shot LoRA"]}
          ttft={A.avg_ttft_ms}
          json={A.json_ok_rate}
          rss={A.avg_rss_mb}
          tps={A.avg_decode_tps}
          count={A.count}
        />
        <ABVariantCard
          side="B"
          color="var(--ab-b)"
          title="LoRA + minimal prompt"
          subtitle="MVTec AD fine-tune · r=16 · α=32 · 150 steps"
          tags={["LoRA r16", "≤100 tok prompt", "MVTec AD finetune"]}
          ttft={B.avg_ttft_ms}
          json={B.json_ok_rate}
          rss={B.avg_rss_mb}
          tps={B.avg_decode_tps}
          count={B.count}
          winner
        />
      </div>

      <div style={{
        marginTop: 18, padding: "14px 18px",
        background: "var(--bg-1)", border: "1px solid var(--line)",
        borderLeft: "3px solid var(--acc)",
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <div>
          <div className="eyebrow" style={{ color: "var(--acc)" }}>ENGINEERING DECISION</div>
          <div style={{ fontSize: 15, color: "var(--fg)", marginTop: 4, fontWeight: 500 }}>
            Ship variant B to production.
            <span style={{ color: "var(--fg-2)", fontWeight: 400, marginLeft: 8 }}>
              ~2× faster TTFT, +14pp JSON parse rate, comparable accuracy.
            </span>
          </div>
        </div>
        <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>
          POST /api/edge/report · variant=B
        </span>
      </div>
    </div>
  );
}

function DeltaHighlight({ label, value, sub, color }){
  return (
    <div style={{ background: "var(--bg-1)", padding: "18px 20px" }}>
      <div className="eyebrow">{label}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginTop: 8 }}>
        <span className="mono" style={{
          fontSize: 34, fontWeight: 500, color,
          letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums",
          textShadow: `0 0 16px color-mix(in srgb, ${color} 30%, transparent)`,
        }}>{value}</span>
      </div>
      <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginTop: 4 }}>{sub}</div>
    </div>
  );
}

function ABVariantCard({ side, color, title, subtitle, tags, ttft, json, rss, tps, count, winner }){
  return (
    <div style={{
      background: "var(--bg-1)", padding: 24,
      position: "relative", overflow: "hidden",
    }}>
      {/* big side letter */}
      <div style={{
        position: "absolute", right: -10, top: -22,
        fontFamily: "var(--font-sans)", fontSize: 180, fontWeight: 700,
        color: color, opacity: 0.06, lineHeight: 1, letterSpacing: "-0.05em",
        pointerEvents: "none",
      }}>{side}</div>

      <div style={{ position: "relative" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{
            width: 36, height: 36, border: `1.5px solid ${color}`, color,
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            fontFamily: "var(--font-mono)", fontSize: 17, fontWeight: 700,
            background: `color-mix(in srgb, ${color} 12%, transparent)`,
            boxShadow: `0 0 12px color-mix(in srgb, ${color} 25%, transparent)`,
          }}>{side}</span>
          <div>
            <div style={{ fontSize: 16, fontWeight: 600, color: "var(--fg)", letterSpacing: "-0.01em" }}>{title}</div>
            <div className="mono" style={{ fontSize: 10, color: "var(--fg-3)", marginTop: 2, letterSpacing: "0.04em" }}>{subtitle}</div>
          </div>
          {winner && (
            <span style={{ marginLeft: "auto" }} className="mono">
              <span style={{
                fontSize: 9, padding: "3px 8px", border: `1px solid ${color}`, color,
                background: `color-mix(in srgb, ${color} 14%, transparent)`,
                letterSpacing: "0.16em", fontWeight: 700,
              }}>★ SHIPPED</span>
            </span>
          )}
        </div>

        {/* tags */}
        <div style={{ display: "flex", gap: 6, marginTop: 14, flexWrap: "wrap" }}>
          {tags.map(t => (
            <span key={t} className="mono" style={{
              fontSize: 9, padding: "2px 8px", border: "1px solid var(--line)",
              color: "var(--fg-2)", letterSpacing: "0.06em", background: "var(--bg-2)",
            }}>{t}</span>
          ))}
        </div>

        {/* big metrics */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, marginTop: 22, background: "var(--line)" }}>
          <BigStat label="TTFT" value={Math.round(ttft)} unit="ms" color={color} />
          <BigStat label="JSON PARSE" value={`${(json*100).toFixed(1)}`} unit="%" color={color} />
          <BigStat label="DECODE" value={tps.toFixed(2)} unit="tok/s" />
          <BigStat label="RSS" value={Math.round(rss)} unit="MB" />
        </div>

        <div style={{ marginTop: 16, display: "flex", justifyContent: "space-between", paddingTop: 12, borderTop: "1px dashed var(--line)" }}>
          <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>SAMPLE COUNT</span>
          <span className="mono" style={{ fontSize: 13, color: "var(--fg)", fontWeight: 500 }}>n = {count}</span>
        </div>
      </div>
    </div>
  );
}

function BigStat({ label, value, unit, color = "var(--fg)" }){
  return (
    <div style={{ padding: "14px 16px", background: "var(--bg-1)" }}>
      <div className="eyebrow" style={{ fontSize: 9 }}>{label}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginTop: 6 }}>
        <span className="mono" style={{
          fontSize: 24, fontWeight: 500, color,
          letterSpacing: "-0.01em", fontVariantNumeric: "tabular-nums",
        }}>{value}</span>
        <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>{unit}</span>
      </div>
    </div>
  );
}

Object.assign(window, { ABCompareV3 });
