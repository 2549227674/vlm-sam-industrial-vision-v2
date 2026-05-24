// V4 mock data — matches API_CONTRACT v1.2
// 15 MVTec AD categories · 4 variant keys · Chrome-trace generation · 4-variant buildStats()

import type { DefectRead, MvtecCategory, TraceEvent, VariantKey } from "@/types/defect";
import type { DashboardStatsLike, VariantMetrics } from "@/types/stats";

// Backwards-compat alias for v2 components
export type { VariantMetrics as MockAbMetrics };

// ── MVTec AD categories ────────────────────────────────────────────────────

export const MVTEC_CATEGORIES = [
  "bottle", "cable", "capsule", "carpet", "grid",
  "hazelnut", "leather", "metal_nut", "pill", "screw",
  "tile", "toothbrush", "transistor", "wood", "zipper",
] as const;

export const CATEGORY_LABEL: Record<string, string> = {
  bottle: "Bottle", cable: "Cable", capsule: "Capsule", carpet: "Carpet",
  grid: "Grid", hazelnut: "Hazelnut", leather: "Leather", metal_nut: "Metal nut",
  pill: "Pill", screw: "Screw", tile: "Tile", toothbrush: "Toothbrush",
  transistor: "Transistor", wood: "Wood", zipper: "Zipper",
};

export const DEFECT_TYPES: Record<string, string[]> = {
  bottle: ["broken_large", "broken_small", "contamination"],
  cable: ["bent_wire", "cable_swap", "combined", "cut_inner_insulation", "cut_outer_insulation", "missing_cable", "missing_wire", "poke_insulation"],
  capsule: ["crack", "faulty_imprint", "poke", "scratch", "squeeze"],
  carpet: ["color", "cut", "hole", "metal_contamination", "thread"],
  grid: ["bent", "broken", "glue", "metal_contamination", "thread"],
  hazelnut: ["crack", "cut", "hole", "print"],
  leather: ["color", "cut", "fold", "glue", "poke"],
  metal_nut: ["bent", "color", "flip", "scratch", "thread"],
  pill: ["color", "combined", "contamination", "crack", "faulty_imprint", "pill_type", "scratch"],
  screw: ["manipulated_front", "scratch_head", "scratch_neck", "thread_side", "thread_top"],
  tile: ["crack", "glue_strip", "gray_stroke", "oil", "rough"],
  toothbrush: ["defective"],
  transistor: ["bent_lead", "cut_lead", "damaged_case", "misplaced"],
  wood: ["color", "combined", "hole", "liquid", "scratch"],
  zipper: ["broken_teeth", "fabric_border", "fabric_interior", "rough", "split_teeth", "squeezed_teeth"],
};

// ── Variants ───────────────────────────────────────────────────────────────

export const SEVERITIES = ["low", "medium", "high"] as const;
const SEVERITY_WEIGHTS = [0.55, 0.30, 0.15];

export const VARIANTS = ["2B_base", "2B_lora", "4B_base", "4B_lora"] as const;
const VARIANT_WEIGHTS = [0.20, 0.45, 0.10, 0.25];
export const LINES = ["L1", "L2", "L3", "L4"];

export const VARIANT_LABEL: Record<string, string> = {
  "2B_base": "2B · Base",
  "2B_lora": "2B · LoRA",
  "4B_base": "4B · Base",
  "4B_lora": "4B · LoRA",
  A: "A (legacy)", B: "B (legacy)",
};

export const VARIANT_PROFILE: Record<string, {
  ttftRange: [number, number]; tpsRange: [number, number]; promptTok: [number, number];
  outTok: [number, number]; rssRange: [number, number]; jsonOk: number; color: string;
}> = {
  "2B_base": { ttftRange: [1900, 2500], tpsRange: [10.6, 12.0], promptTok: [780, 1480], outTok: [38, 86], rssRange: [3050, 3200], jsonOk: 0.81, color: "#9aa4ff" },
  "2B_lora": { ttftRange: [900, 1350], tpsRange: [11.4, 12.6], promptTok: [60, 96], outTok: [38, 76], rssRange: [3020, 3140], jsonOk: 0.95, color: "var(--acc)" },
  "4B_base": { ttftRange: [3200, 4100], tpsRange: [7.4, 8.6], promptTok: [780, 1480], outTok: [48, 96], rssRange: [8600, 8950], jsonOk: 0.88, color: "#ff9f6c" },
  "4B_lora": { ttftRange: [1900, 2400], tpsRange: [8.2, 9.0], promptTok: [60, 96], outTok: [44, 92], rssRange: [8550, 8820], jsonOk: 0.97, color: "#7cdcff" },
};

// ── Variant helpers ─────────────────────────────────────────────────────────

export function normalizeVariant(v: string): string {
  if (v === "A") return "2B_base";
  if (v === "B") return "2B_lora";
  return v;
}

export function variantLabel(v: string): string {
  return VARIANT_LABEL[v] || v;
}

export function variantColor(v: string): string {
  return VARIANT_PROFILE[normalizeVariant(v)]?.color || "var(--fg-2)";
}

export function variantModel(v: string): string {
  return normalizeVariant(v).startsWith("4B") ? "Qwen3-VL-4B" : "Qwen3-VL-2B";
}

export function variantIsLora(v: string): boolean {
  return normalizeVariant(v).endsWith("_lora");
}

// ── Description fragments ───────────────────────────────────────────────────

function descriptionFor(cat: string, dt: string): string {
  const fragMap: Record<string, string> = {
    crack: "linear crack along surface, depth medium",
    color: "anomalous color patch, likely oxidation or stain",
    scratch: "linear scratch, horizontal orientation",
    hole: "perforation through material surface",
    cut: "clean longitudinal cut, edge sharp",
    bent: "geometric deformation, concentricity off",
    flip: "specimen orientation inverted",
    contamination: "foreign particle adhering to surface",
    faulty_imprint: "imprint blurred, possible double-stamp",
    rough: "surface texture coarse beyond tolerance",
    glue: "adhesive residue, contour irregular",
    poke: "indentation point, tool mark suspected",
    fold: "fold line, material doubled",
    print: "print pattern damaged",
    squeeze: "deformation along axis, pressure mark",
    broken_large: "large fragment missing, sharp edge",
    broken_small: "small chip missing, isolated",
    metal_contamination: "metallic foreign object embedded",
    misplaced: "component offset from solder pad",
    bent_lead: "lead deformation, pitch broken",
  };
  return fragMap[dt] || `${dt.replace(/_/g, " ")} — awaiting human review.`;
}

// ── Utility ─────────────────────────────────────────────────────────────────

function rand(min: number, max: number): number {
  return Math.random() * (max - min) + min;
}

function pick<T>(arr: readonly T[] | T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function pickWeighted<T>(arr: readonly T[], weights: number[]): T {
  const r = Math.random();
  let acc = 0;
  for (let i = 0; i < arr.length; i++) {
    acc += weights[i];
    if (r < acc) return arr[i];
  }
  return arr[arr.length - 1];
}

function uid(n = 4): string {
  return Array.from({ length: n }, () =>
    Math.random().toString(16).slice(2, 6)
  ).join("");
}

let _idCounter = 84211;
function nextId(): number {
  return ++_idCounter;
}

function makeBboxes() {
  const n = Math.floor(rand(1, 5));
  const out: Array<{ x: number; y: number; w: number; h: number }> = [];
  for (let i = 0; i < n; i++) {
    const w = rand(0.06, 0.25);
    const h = rand(0.06, 0.22);
    out.push({
      x: +rand(0.05, 1 - w - 0.05).toFixed(3),
      y: +rand(0.05, 1 - h - 0.05).toFixed(3),
      w: +w.toFixed(3),
      h: +h.toFixed(3),
    });
  }
  return out;
}

// ── Trace events (Chrome-trace format) ──────────────────────────────────────

export function makeTraceEvents(pipeline_ms: { efficientad: number; fastsam: number; qwen3vl: number }, variant: string): TraceEvent[] {
  const v = normalizeVariant(variant);
  const events: TraceEvent[] = [];
  let cur = 0;
  const ms = (x: number) => Math.round(x * 1000);

  // T1 capture
  const capture = ms(rand(6, 14));
  events.push({ name: "V4L2.ioctl", tid: "T1.capture", ph: "X", ts: cur, dur: capture, cat: "io" });
  cur += capture;

  // T2 pipeline → NPU.0 EfficientAD
  const rga = ms(rand(1.2, 2.6));
  events.push({ name: "RGA.resize_BGR2RGB", tid: "T2.pipeline", ph: "X", ts: cur, dur: rga, cat: "rga" });
  cur += rga;
  const eff = ms(pipeline_ms.efficientad);
  events.push({ name: "rknn_run · EfficientAD-S", tid: "T2.pipeline", ph: "X", ts: cur, dur: eff, cat: "infer" });
  events.push({ name: "EfficientAD-S [FP16]", tid: "NPU.core0", ph: "X", ts: cur, dur: eff, cat: "npu" });
  events.push({ name: "anomaly_score · postproc", tid: "CPU.A76_0", ph: "X", ts: cur, dur: ms(rand(0.4, 0.9)), cat: "cpu" });
  cur += eff + 200;

  // T2 → NPU.1 FastSAM
  const fs = ms(pipeline_ms.fastsam);
  events.push({ name: "rknn_run · FastSAM-s", tid: "T2.pipeline", ph: "X", ts: cur, dur: fs, cat: "infer" });
  events.push({ name: "FastSAM-s [FP16]", tid: "NPU.core1", ph: "X", ts: cur, dur: fs, cat: "npu" });
  events.push({ name: "bbox.nms+filter", tid: "CPU.A76_1", ph: "X", ts: cur + fs - ms(4), dur: ms(rand(1.8, 3.6)), cat: "cpu" });
  cur += fs + 400;

  // T2 → T3 VLM
  events.push({ name: "BoundedQueue.push", tid: "T2.pipeline", ph: "X", ts: cur, dur: 80, cat: "sync" });
  events.push({ name: "BoundedQueue.pop", tid: "T3.vlm", ph: "X", ts: cur + 80, dur: 120, cat: "sync" });
  cur += 240;

  const qwen = pipeline_ms.qwen3vl;
  const isLora = v.endsWith("_lora");
  const promptFrac = isLora ? 0.55 : 0.62;
  const promptDur = ms(qwen * promptFrac);
  const decodeDur = ms(qwen) - promptDur;
  const promptName = `rkllm prompt (${isLora ? "~78 tok · LoRA" : "~1140 tok"})`;
  events.push({ name: promptName, tid: "T3.vlm", ph: "X", ts: cur, dur: promptDur, cat: "vlm-prompt" });
  events.push({ name: "Qwen3-VL prompt", tid: "NPU.core2", ph: "X", ts: cur, dur: promptDur, cat: "vlm-prompt" });
  events.push({ name: "vision_encoder", tid: "NPU.core2", ph: "X", ts: cur, dur: ms(180), cat: "vlm-encode" });
  cur += promptDur;

  events.push({ name: "rkllm decode loop", tid: "T3.vlm", ph: "X", ts: cur, dur: decodeDur, cat: "vlm-decode" });
  events.push({ name: "Qwen3-VL decode", tid: "NPU.core2", ph: "X", ts: cur, dur: decodeDur, cat: "vlm-decode" });
  cur += decodeDur;
  events.push({ name: "json.loads · validate", tid: "T3.vlm", ph: "X", ts: cur, dur: ms(rand(0.8, 1.8)), cat: "cpu" });
  cur += ms(2);

  // T4 upload
  events.push({ name: "BoundedQueue.push", tid: "T3.vlm", ph: "X", ts: cur, dur: 80, cat: "sync" });
  events.push({ name: "BoundedQueue.pop", tid: "T4.upload", ph: "X", ts: cur + 80, dur: 120, cat: "sync" });
  cur += 240;
  const up = ms(rand(60, 220));
  events.push({ name: "curl · POST /api/edge/report", tid: "T4.upload", ph: "X", ts: cur, dur: up, cat: "io" });
  events.push({ name: "tcp.send", tid: "CPU.A55_0", ph: "X", ts: cur, dur: up * 0.4, cat: "cpu" });

  return events;
}

// ── Defect factory ──────────────────────────────────────────────────────────

export function makeDefect(opts: Partial<{
  ts: Date; category: string; variant: string; severity: string; id: number; defect_type: string;
}> = {}): DefectRead {
  const category = (opts.category ?? pick(MVTEC_CATEGORIES)) as MvtecCategory;
  const variant = normalizeVariant(opts.variant ?? pickWeighted(VARIANTS, VARIANT_WEIGHTS)) as VariantKey;
  const severity = (opts.severity ?? pickWeighted(SEVERITIES, SEVERITY_WEIGHTS)) as "low" | "medium" | "high";
  const dt = opts.defect_type ?? pick(DEFECT_TYPES[category] ?? ["defective"]);
  const ts = opts.ts ?? new Date(Date.now() - Math.floor(rand(0, 1000 * 60 * 60 * 23)));
  const profile = VARIANT_PROFILE[variant] || VARIANT_PROFILE["2B_lora"];
  const json_ok = Math.random() < profile.jsonOk;

  const qwenBase = variant.startsWith("4B") ? [3200, 4800] : [1800, 2700];
  const pipeline_ms = {
    efficientad: +rand(3.2, 6.1).toFixed(2),
    fastsam: +rand(38, 62).toFixed(1),
    qwen3vl: +rand(qwenBase[0], qwenBase[1]).toFixed(0),
  };

  return {
    id: opts.id ?? nextId(),
    line_id: pick(LINES),
    category,
    defect_type: dt,
    severity,
    confidence: +rand(0.62, 0.99).toFixed(3),
    anomaly_score: +rand(1.2, 5.4).toFixed(2),
    bboxes: makeBboxes(),
    description: descriptionFor(category, dt),
    variant,
    edge_ts: ts.toISOString(),
    server_ts: new Date(ts.getTime() + Math.floor(rand(80, 600))).toISOString(),
    image_url: `/static/defects/${dateKey(ts)}/${uid(8)}.jpg`,
    pipeline_ms,
    vlm_metrics: {
      ttft_ms: Math.floor(rand(...profile.ttftRange)),
      decode_tps: +rand(...profile.tpsRange).toFixed(2),
      prompt_tokens: Math.floor(rand(...profile.promptTok)),
      output_tokens: Math.floor(rand(...profile.outTok)),
      rss_mb: Math.floor(rand(...profile.rssRange)),
      json_parse_ok: json_ok,
    },
    trace_events: makeTraceEvents(pipeline_ms, variant),
    schema_version: "v1",
  };
}

export function seedDefects(n = 120): DefectRead[] {
  const out: DefectRead[] = [];
  const now = Date.now();
  for (let i = 0; i < n; i++) {
    const ts = new Date(now - Math.floor(Math.pow(i / n, 0.6) * 1000 * 60 * 60 * 24));
    out.push(makeDefect({ ts }));
  }
  return out.sort((a, b) => new Date(b.edge_ts).getTime() - new Date(a.edge_ts).getTime());
}

// ── Stats ───────────────────────────────────────────────────────────────────

export interface MockStats extends DashboardStatsLike {
  total: number;
  today_defects: number;
  today_high: number;
  by_category: Record<string, number>;
  by_severity: Record<string, number>;
  ab_compare: Record<string, VariantMetrics>;
}

export function buildStats(defects: DefectRead[]): MockStats {
  const by_category: Record<string, number> = {};
  for (const c of MVTEC_CATEGORIES) by_category[c] = 0;
  const by_severity: Record<string, number> = { low: 0, medium: 0, high: 0 };

  const ab: Record<string, VariantMetrics> = {};
  for (const v of VARIANTS) {
    ab[v] = { count: 0, json_ok: 0, json_ok_rate: 0, ttft: 0, avg_ttft_ms: 0, tps: 0, avg_decode_tps: 0, rss: 0, avg_rss_mb: 0, prompt: 0, avg_prompt_tokens: 0, output: 0, avg_output_tokens: 0 };
  }

  for (const d of defects) {
    const v = normalizeVariant(d.variant);
    if (by_category[d.category] != null) by_category[d.category]++;
    by_severity[d.severity]++;
    if (!ab[v]) {
      ab[v] = { count: 0, json_ok: 0, json_ok_rate: 0, ttft: 0, avg_ttft_ms: 0, tps: 0, avg_decode_tps: 0, rss: 0, avg_rss_mb: 0, prompt: 0, avg_prompt_tokens: 0, output: 0, avg_output_tokens: 0 };
    }
    const a = ab[v];
    a.count++;
    if (d.vlm_metrics?.json_parse_ok) a.json_ok++;
    a.ttft += d.vlm_metrics?.ttft_ms ?? 0;
    a.tps += d.vlm_metrics?.decode_tps ?? 0;
    a.rss += d.vlm_metrics?.rss_mb ?? 0;
    a.prompt += d.vlm_metrics?.prompt_tokens ?? 0;
    a.output += d.vlm_metrics?.output_tokens ?? 0;
  }

  for (const k of Object.keys(ab)) {
    const a = ab[k];
    if (a.count) {
      a.json_ok_rate = a.json_ok / a.count;
      a.avg_ttft_ms = a.ttft / a.count;
      a.avg_decode_tps = a.tps / a.count;
      a.avg_rss_mb = a.rss / a.count;
      a.avg_prompt_tokens = a.prompt / a.count;
      a.avg_output_tokens = a.output / a.count;
    } else {
      a.json_ok_rate = 0; a.avg_ttft_ms = 0; a.avg_decode_tps = 0;
      a.avg_rss_mb = 0; a.avg_prompt_tokens = 0; a.avg_output_tokens = 0;
    }
  }

  const avg_pipeline_ms = defects.length
    ? {
        efficientad: defects.reduce((s, d) => s + d.pipeline_ms.efficientad, 0) / defects.length,
        fastsam: defects.reduce((s, d) => s + d.pipeline_ms.fastsam, 0) / defects.length,
        qwen3vl: defects.reduce((s, d) => s + d.pipeline_ms.qwen3vl, 0) / defects.length,
      }
    : undefined;

  return {
    total: defects.length,
    today_defects: defects.length,
    today_high: defects.filter(d => d.severity === "high").length,
    by_category,
    by_severity,
    ab_compare: ab,
    avg_pipeline_ms,
  };
}

// ── Formatting helpers ──────────────────────────────────────────────────────

export function fmtTime(d: Date | string): string {
  if (typeof d === "string") d = new Date(d);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

export function fmtDateTime(d: Date | string): string {
  if (typeof d === "string") d = new Date(d);
  const yy = d.getFullYear();
  const mo = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yy}-${mo}-${dd} ${fmtTime(d)}`;
}

export function fmtNumber(n: number | null | undefined, opts: { digits?: number; sep?: string } = {}): string {
  if (n == null || isNaN(n)) return "—";
  const { digits = 0, sep = "," } = opts;
  const fixed = Number(n).toFixed(digits);
  const [a, b] = fixed.split(".");
  const out = a.replace(/\B(?=(\d{3})+(?!\d))/g, sep);
  return b ? `${out}.${b}` : out;
}

function dateKey(d: Date): string {
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}`;
}

// ── Timeline ────────────────────────────────────────────────────────────────

export interface TimelineBucket {
  ts: Date;
  count: number;
  hi: number;
}

export function buildTimeline(defects: DefectRead[], hours = 24): TimelineBucket[] {
  const buckets: TimelineBucket[] = [];
  const now = Date.now();
  for (let h = hours - 1; h >= 0; h--) {
    const t = now - h * 3600_000;
    const dt = new Date(t);
    dt.setMinutes(0, 0, 0);
    buckets.push({ ts: dt, count: 0, hi: 0 });
  }
  for (const d of defects) {
    const dt = new Date(d.edge_ts).getTime();
    for (const b of buckets) {
      if (dt >= b.ts.getTime() && dt < b.ts.getTime() + 3600_000) {
        b.count++;
        if (d.severity === "high") b.hi++;
        break;
      }
    }
  }
  return buckets;
}
