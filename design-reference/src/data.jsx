// Mock data + simulated WS event stream. Mirrors backend schema (frontend/src/types/defect.ts).
// Adds trace_events[] in Chrome-trace JSON format for Profile page.

const DEFECT_TYPES = {
  metal_nut: ["scratch", "color", "bent", "flip", "thread"],
  screw: ["scratch_neck", "scratch_head", "thread_top", "thread_side", "manipulated_front"],
  pill: ["color", "crack", "contamination", "faulty_imprint", "scratch", "pill_type"],
};
const SEVERITIES = ["low", "medium", "high"];
const SEVERITY_WEIGHTS = [0.55, 0.30, 0.15];
const VARIANTS = ["A", "B"];
const LINES = ["L1", "L2", "L3"];

function rand(min, max){ return Math.random() * (max - min) + min; }
function pick(arr){ return arr[Math.floor(Math.random() * arr.length)]; }
function pickWeighted(arr, w){
  const r = Math.random();
  let acc = 0;
  for (let i = 0; i < arr.length; i++){ acc += w[i]; if (r < acc) return arr[i]; }
  return arr[arr.length - 1];
}
function uid(n = 4){
  return Array.from({length: n}, () => Math.random().toString(16).slice(2, 6)).join("");
}

let _idCounter = 84211;
function nextId(){ return ++_idCounter; }

function makeBboxes(){
  const n = Math.floor(rand(1, 5));
  const out = [];
  for (let i = 0; i < n; i++){
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

// Generate Chrome-trace events for a single frame's pipeline run.
// 4 software threads (T1-T4) + 3 NPU cores + 8 CPU cores (A76×4 + A55×4).
// All durations in microseconds.
function makeTraceEvents(pipeline_ms, variant){
  const events = [];
  let cursor_us = 0;
  const ms = v => Math.round(v * 1000); // ms → us

  // T1: Capture thread
  const captureDur = ms(rand(6, 14));
  events.push({ name: "V4L2.ioctl", tid: "T1.capture", ph: "X", ts: cursor_us, dur: captureDur, cat: "io" });
  events.push({ name: "mmap_buffer", tid: "T1.capture", ph: "X", ts: cursor_us + captureDur - 200, dur: 180, cat: "mem" });
  cursor_us += captureDur;

  // T2: Pipeline thread — RGA preprocess + EfficientAD on NPU0
  const rgaDur = ms(rand(1.2, 2.6));
  events.push({ name: "RGA.resize_BGR2RGB", tid: "T2.pipeline", ph: "X", ts: cursor_us, dur: rgaDur, cat: "rga" });
  cursor_us += rgaDur;
  const effDur = ms(pipeline_ms.efficientad);
  events.push({ name: "rknn_run · EfficientAD-S", tid: "T2.pipeline", ph: "X", ts: cursor_us, dur: effDur, cat: "infer" });
  events.push({ name: "EfficientAD-S [INT8]",     tid: "NPU.core0",  ph: "X", ts: cursor_us, dur: effDur, cat: "npu" });
  events.push({ name: "anomaly_score · postproc", tid: "CPU.A76_0",  ph: "X", ts: cursor_us, dur: ms(rand(0.4, 0.9)), cat: "cpu" });
  cursor_us += effDur + 200;

  // T2 continued: FastSAM on NPU1
  const fsDur = ms(pipeline_ms.fastsam);
  events.push({ name: "rknn_run · FastSAM-s",  tid: "T2.pipeline", ph: "X", ts: cursor_us, dur: fsDur, cat: "infer" });
  events.push({ name: "FastSAM-s [INT8]",      tid: "NPU.core1",   ph: "X", ts: cursor_us, dur: fsDur, cat: "npu" });
  // bbox post-processing on CPU
  const bboxStart = cursor_us + fsDur - ms(4);
  events.push({ name: "bbox.nms+filter",       tid: "CPU.A76_1",   ph: "X", ts: bboxStart, dur: ms(rand(1.8, 3.6)), cat: "cpu" });
  events.push({ name: "vlm_bbox_ref · 5-lvl",  tid: "CPU.A76_1",   ph: "X", ts: bboxStart + ms(2), dur: ms(rand(0.6, 1.4)), cat: "cpu" });
  cursor_us += fsDur + 400;

  // Hand-off to T3 — VLM worker. Queue write.
  events.push({ name: "BoundedQueue.push", tid: "T2.pipeline", ph: "X", ts: cursor_us, dur: 80, cat: "sync" });
  events.push({ name: "BoundedQueue.pop",  tid: "T3.vlm",      ph: "X", ts: cursor_us + 80, dur: 120, cat: "sync" });
  cursor_us += 240;

  // T3: VLM — prompt phase (~10-15% of qwen3vl latency)
  const qwenTotal = pipeline_ms.qwen3vl;
  const promptDur = ms(variant === "A" ? qwenTotal * 0.62 : qwenTotal * 0.55);  // TTFT roughly
  const decodeDur = ms(qwenTotal) - promptDur;
  events.push({ name: variant === "A" ? "rkllm prompt (1140 tok)" : "rkllm prompt (78 tok · LoRA)",
                tid: "T3.vlm", ph: "X", ts: cursor_us, dur: promptDur, cat: "vlm-prompt" });
  events.push({ name: "Qwen3-VL prompt",
                tid: "NPU.core2", ph: "X", ts: cursor_us, dur: promptDur, cat: "vlm-prompt" });
  // image encoder runs on NPU2 first
  events.push({ name: "vision_encoder",
                tid: "NPU.core2", ph: "X", ts: cursor_us, dur: ms(180), cat: "vlm-encode" });
  cursor_us += promptDur;

  // Decode phase
  events.push({ name: "rkllm decode loop", tid: "T3.vlm",    ph: "X", ts: cursor_us, dur: decodeDur, cat: "vlm-decode" });
  events.push({ name: "Qwen3-VL decode",   tid: "NPU.core2", ph: "X", ts: cursor_us, dur: decodeDur, cat: "vlm-decode" });
  // sample tokens on CPU
  const tokN = Math.floor(rand(38, 86));
  const decodeMs = decodeDur / 1000;
  for (let i = 0; i < Math.min(tokN, 80); i++){
    const t = cursor_us + Math.floor((i / tokN) * decodeDur);
    events.push({ name: "softmax+sample", tid: "CPU.A76_2", ph: "X", ts: t, dur: 240, cat: "cpu" });
  }
  cursor_us += decodeDur;

  // JSON parse
  events.push({ name: "json.loads · validate", tid: "T3.vlm", ph: "X", ts: cursor_us, dur: ms(rand(0.8, 1.8)), cat: "cpu" });
  cursor_us += ms(2);

  // T4: Upload
  events.push({ name: "BoundedQueue.push", tid: "T3.vlm",    ph: "X", ts: cursor_us, dur: 80, cat: "sync" });
  events.push({ name: "BoundedQueue.pop",  tid: "T4.upload", ph: "X", ts: cursor_us + 80, dur: 120, cat: "sync" });
  cursor_us += 240;
  const uploadDur = ms(rand(60, 220));
  events.push({ name: "curl_easy_perform · POST /api/edge/report",
                tid: "T4.upload", ph: "X", ts: cursor_us, dur: uploadDur, cat: "io" });
  events.push({ name: "tcp.send",
                tid: "CPU.A55_0", ph: "X", ts: cursor_us, dur: uploadDur * 0.4, cat: "cpu" });
  // small idle activity on A55
  for (let i = 0; i < 3; i++){
    events.push({ name: "scheduler.tick", tid: `CPU.A55_${i+1}`, ph: "X",
                  ts: Math.floor(rand(0, cursor_us)), dur: ms(rand(0.3, 0.9)), cat: "cpu" });
  }
  cursor_us += uploadDur;

  return events;
}

function makeDefect(opts = {}){
  const category = opts.category ?? pick(["metal_nut", "screw", "pill"]);
  const variant = opts.variant ?? pick(VARIANTS);
  const severity = opts.severity ?? pickWeighted(SEVERITIES, SEVERITY_WEIGHTS);
  const dt = opts.defect_type ?? pick(DEFECT_TYPES[category]);
  const ts = opts.ts ?? new Date(Date.now() - Math.floor(rand(0, 1000 * 60 * 60 * 23)));
  const json_ok = Math.random() < (variant === "A" ? 0.81 : 0.95);
  const pipeline_ms = {
    efficientad: +rand(3.2, 6.1).toFixed(2),
    fastsam:     +rand(38, 62).toFixed(1),
    qwen3vl:     +rand(1800, 2700).toFixed(0),
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
    edge_ts: ts,
    server_ts: new Date(ts.getTime() + Math.floor(rand(80, 600))),
    image_url: `/static/defects/${dateKey(ts)}/${uid(8)}.jpg`,
    pipeline_ms,
    vlm_metrics: {
      ttft_ms:        Math.floor(variant === "A" ? rand(1900, 2500) : rand(900, 1350)),
      decode_tps:     +(variant === "A" ? rand(10.6, 12.0) : rand(11.4, 12.6)).toFixed(2),
      prompt_tokens:  variant === "A" ? Math.floor(rand(780, 1480)) : Math.floor(rand(60, 96)),
      output_tokens:  Math.floor(rand(38, 86)),
      rss_mb:         Math.floor(variant === "A" ? rand(3050, 3200) : rand(3020, 3140)),
      json_parse_ok:  json_ok,
    },
    trace_events: makeTraceEvents(pipeline_ms, variant),
    schema_version: "v1",
  };
}

function descriptionFor(cat, dt){
  const map = {
    scratch: "表面长条划痕,沿水平方向延伸,纹理深度中等",
    color: "颜色异常斑块,可能由表面氧化或污染物造成",
    bent: "螺母螺纹有明显弯折,影响装配同心度",
    flip: "工件上下翻转,定位姿态错误",
    thread: "螺纹深度异常,疑似车削刀具磨损",
    scratch_neck: "螺纹颈部出现纵向划痕,约 1.2mm",
    scratch_head: "螺帽边缘划伤,呈半圆形分布",
    thread_top: "螺顶螺纹缺损,可能存在加工断刀",
    thread_side: "侧面螺纹不连续,深度异常",
    manipulated_front: "正面被人为修整,螺纹特征模糊",
    crack: "药片表面纵向裂纹,长度约药片直径 1/3",
    contamination: "药片表面附着颗粒杂质,疑似生产线粉尘",
    faulty_imprint: "压印图案不清晰,存在双重压印迹象",
    pill_type: "药片类型不匹配,颜色与基线模板偏差大",
  };
  return map[dt] ?? "异常区域已检出,等待人工复核.";
}

function dateKey(d){
  return `${d.getFullYear()}${String(d.getMonth()+1).padStart(2,"0")}${String(d.getDate()).padStart(2,"0")}`;
}

function fmtTime(d){
  if (typeof d === "string") d = new Date(d);
  const hh = String(d.getHours()).padStart(2,"0");
  const mm = String(d.getMinutes()).padStart(2,"0");
  const ss = String(d.getSeconds()).padStart(2,"0");
  return `${hh}:${mm}:${ss}`;
}
function fmtDateTime(d){
  if (typeof d === "string") d = new Date(d);
  const yy = d.getFullYear();
  const mo = String(d.getMonth()+1).padStart(2,"0");
  const dd = String(d.getDate()).padStart(2,"0");
  return `${yy}-${mo}-${dd} ${fmtTime(d)}`;
}
function fmtNumber(n, opts = {}){
  if (n == null || isNaN(n)) return "—";
  const { digits = 0, sep = "," } = opts;
  const fixed = Number(n).toFixed(digits);
  const [a, b] = fixed.split(".");
  const out = a.replace(/\B(?=(\d{3})+(?!\d))/g, sep);
  return b ? `${out}.${b}` : out;
}

function seedDefects(n = 120){
  const out = [];
  const now = Date.now();
  for (let i = 0; i < n; i++){
    const ts = new Date(now - Math.floor(Math.pow(i / n, 0.6) * 1000 * 60 * 60 * 24));
    out.push(makeDefect({ ts }));
  }
  return out.sort((a, b) => b.edge_ts - a.edge_ts);
}

function buildTimeline(defects, hours = 24){
  const buckets = [];
  const now = Date.now();
  for (let h = hours - 1; h >= 0; h--){
    const t = now - h * 3600_000;
    const dt = new Date(t);
    dt.setMinutes(0, 0, 0);
    buckets.push({ ts: dt, count: 0, hi: 0 });
  }
  for (const d of defects){
    const dt = d.edge_ts instanceof Date ? d.edge_ts : new Date(d.edge_ts);
    for (const b of buckets){
      if (dt.getTime() >= b.ts.getTime() && dt.getTime() < b.ts.getTime() + 3600_000){
        b.count++;
        if (d.severity === "high") b.hi++;
        break;
      }
    }
  }
  return buckets;
}

function buildStats(defects){
  const by_category = { metal_nut: 0, screw: 0, pill: 0 };
  const by_severity = { low: 0, medium: 0, high: 0 };
  const ab = {
    A: { count: 0, json_ok: 0, ttft: 0, tps: 0, rss: 0, prompt: 0 },
    B: { count: 0, json_ok: 0, ttft: 0, tps: 0, rss: 0, prompt: 0 },
  };
  for (const d of defects){
    by_category[d.category]++;
    by_severity[d.severity]++;
    const a = ab[d.variant];
    a.count++;
    a.json_ok += d.vlm_metrics.json_parse_ok ? 1 : 0;
    a.ttft += d.vlm_metrics.ttft_ms;
    a.tps  += d.vlm_metrics.decode_tps;
    a.rss  += d.vlm_metrics.rss_mb;
    a.prompt += d.vlm_metrics.prompt_tokens;
  }
  const today_hi = defects.filter(d => d.severity === "high").length;
  for (const k of ["A", "B"]){
    const a = ab[k];
    if (a.count){
      a.json_ok_rate     = a.json_ok / a.count;
      a.avg_ttft_ms      = a.ttft / a.count;
      a.avg_decode_tps   = a.tps / a.count;
      a.avg_rss_mb       = a.rss / a.count;
      a.avg_prompt_tokens = a.prompt / a.count;
    } else {
      a.json_ok_rate = 0; a.avg_ttft_ms = 0; a.avg_decode_tps = 0; a.avg_rss_mb = 0; a.avg_prompt_tokens = 0;
    }
  }
  return {
    total: defects.length,
    today_defects: defects.length,
    today_high: today_hi,
    by_category,
    by_severity,
    ab_compare: ab,
  };
}

Object.assign(window, {
  makeDefect, seedDefects, buildTimeline, buildStats, makeTraceEvents,
  fmtTime, fmtDateTime, fmtNumber,
  DEFECT_TYPES, SEVERITIES, VARIANTS, LINES,
});
