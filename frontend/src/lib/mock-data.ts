// V2 mock data — translated from design-reference/src/data.jsx
// Provides realistic fallback data when API is unavailable.

import type { DefectRead } from '@/types/defect';

const DEFECT_TYPES: Record<string, string[]> = {
  metal_nut: ['scratch', 'color', 'bent', 'flip', 'thread'],
  screw: ['scratch_neck', 'scratch_head', 'thread_top', 'thread_side', 'manipulated_front'],
  pill: ['color', 'crack', 'contamination', 'faulty_imprint', 'scratch', 'pill_type'],
};

const SEVERITIES: Array<'low' | 'medium' | 'high'> = ['low', 'medium', 'high'];
const SEVERITY_WEIGHTS = [0.55, 0.30, 0.15];
const VARIANTS: Array<'A' | 'B'> = ['A', 'B'];
const LINES = ['L1', 'L2', 'L3'];

const DESCRIPTIONS: Record<string, string> = {
  scratch: '表面长条划痕，沿水平方向延伸，纹理深度中等',
  color: '颜色异常斑块，可能由表面氧化或污染物造成',
  bent: '螺母螺纹有明显弯折，影响装配同心度',
  flip: '工件上下翻转，定位姿态错误',
  thread: '螺纹深度异常，疑似车削刀具磨损',
  scratch_neck: '螺纹颈部出现纵向划痕，约 1.2mm',
  scratch_head: '螺帽边缘划伤，呈半圆形分布',
  thread_top: '螺顶螺纹缺损，可能存在加工断刀',
  thread_side: '侧面螺纹不连续，深度异常',
  manipulated_front: '正面被人为修整，螺纹特征模糊',
  crack: '药片表面纵向裂纹，长度约药片直径 1/3',
  contamination: '药片表面附着颗粒杂质，疑似生产线粉尘',
  faulty_imprint: '压印图案不清晰，存在双重压印迹象',
  pill_type: '药片类型不匹配，颜色与基线模板偏差大',
};

function rand(min: number, max: number): number {
  return Math.random() * (max - min) + min;
}

function pick<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function pickWeighted<T>(arr: T[], weights: number[]): T {
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
  ).join('');
}

function dateKey(d: Date): string {
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
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

export function makeDefect(opts: Partial<{ ts: Date; category: string; variant: string; severity: string; id: number }> = {}): DefectRead {
  const category = (opts.category ?? pick(['metal_nut', 'screw', 'pill'])) as string;
  const variant = (opts.variant ?? pick(VARIANTS)) as 'A' | 'B';
  const severity = (opts.severity ?? pickWeighted(SEVERITIES, SEVERITY_WEIGHTS)) as 'low' | 'medium' | 'high';
  const dt = pick(DEFECT_TYPES[category] ?? ['unknown']);
  const ts = opts.ts ?? new Date(Date.now() - Math.floor(rand(0, 1000 * 60 * 60 * 23)));
  const json_ok = Math.random() < (variant === 'A' ? 0.81 : 0.95);

  return {
    id: opts.id ?? nextId(),
    line_id: pick(LINES),
    category,
    defect_type: dt,
    severity,
    confidence: +rand(0.62, 0.99).toFixed(3),
    anomaly_score: +rand(1.2, 5.4).toFixed(2),
    bboxes: makeBboxes(),
    description: DESCRIPTIONS[dt] ?? '异常区域已检出，等待人工复核。',
    variant,
    edge_ts: ts.toISOString(),
    server_ts: new Date(ts.getTime() + Math.floor(rand(80, 600))).toISOString(),
    image_url: `/static/defects/${dateKey(ts)}/${uid(8)}.jpg`,
    pipeline_ms: {
      efficientad: +rand(3.2, 6.1).toFixed(2),
      fastsam: +rand(38, 62).toFixed(1),
      qwen3vl: +rand(1800, 2700).toFixed(0),
    },
    vlm_metrics: {
      ttft_ms: Math.floor(variant === 'A' ? rand(1900, 2500) : rand(900, 1350)),
      decode_tps: +(variant === 'A' ? rand(10.6, 12.0) : rand(11.4, 12.6)).toFixed(2),
      prompt_tokens: variant === 'A' ? Math.floor(rand(780, 1480)) : Math.floor(rand(60, 96)),
      output_tokens: Math.floor(rand(38, 86)),
      rss_mb: Math.floor(variant === 'A' ? rand(3050, 3200) : rand(3020, 3140)),
      json_parse_ok: json_ok,
    },
    schema_version: 'v1',
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
        if (d.severity === 'high') b.hi++;
        break;
      }
    }
  }
  return buckets;
}

export interface MockAbMetrics {
  count: number;
  json_ok: number;
  json_ok_rate: number;
  ttft: number;
  avg_ttft_ms: number;
  tps: number;
  avg_decode_tps: number;
  rss: number;
  avg_rss_mb: number;
}

export interface MockStats {
  total: number;
  today_defects: number;
  today_high: number;
  by_category: Record<string, number>;
  by_severity: Record<string, number>;
  ab_compare: {
    A: MockAbMetrics;
    B: MockAbMetrics;
  };
}

export function buildStats(defects: DefectRead[]): MockStats {
  const by_category: Record<string, number> = { metal_nut: 0, screw: 0, pill: 0 };
  const by_severity: Record<string, number> = { low: 0, medium: 0, high: 0 };
  const ab: Record<string, MockAbMetrics> = {
    A: { count: 0, json_ok: 0, json_ok_rate: 0, ttft: 0, avg_ttft_ms: 0, tps: 0, avg_decode_tps: 0, rss: 0, avg_rss_mb: 0 },
    B: { count: 0, json_ok: 0, json_ok_rate: 0, ttft: 0, avg_ttft_ms: 0, tps: 0, avg_decode_tps: 0, rss: 0, avg_rss_mb: 0 },
  };

  for (const d of defects) {
    by_category[d.category] = (by_category[d.category] ?? 0) + 1;
    by_severity[d.severity] = (by_severity[d.severity] ?? 0) + 1;
    const a = ab[d.variant];
    a.count++;
    if (d.vlm_metrics?.json_parse_ok) a.json_ok++;
    a.ttft += d.vlm_metrics?.ttft_ms ?? 0;
    a.tps += d.vlm_metrics?.decode_tps ?? 0;
    a.rss += d.vlm_metrics?.rss_mb ?? 0;
  }

  const today_hi = defects.filter(d => d.severity === 'high').length;

  for (const k of ['A', 'B']) {
    const a = ab[k];
    if (a.count) {
      a.json_ok_rate = a.json_ok / a.count;
      a.avg_ttft_ms = a.ttft / a.count;
      a.avg_decode_tps = a.tps / a.count;
      a.avg_rss_mb = a.rss / a.count;
    }
  }

  return {
    total: defects.length,
    today_defects: defects.length,
    today_high: today_hi,
    by_category,
    by_severity,
    ab_compare: { A: ab.A, B: ab.B },
  };
}

// Formatting helpers
export function fmtTime(d: Date | string): string {
  if (typeof d === 'string') d = new Date(d);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const ss = String(d.getSeconds()).padStart(2, '0');
  return `${hh}:${mm}:${ss}`;
}

export function fmtDateTime(d: Date | string): string {
  if (typeof d === 'string') d = new Date(d);
  const yy = d.getFullYear();
  const mo = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yy}-${mo}-${dd} ${fmtTime(d)}`;
}

export function fmtNumber(n: number | null | undefined, opts: { digits?: number; sep?: string } = {}): string {
  if (n == null || isNaN(n)) return '—';
  const { digits = 0, sep = ',' } = opts;
  const fixed = Number(n).toFixed(digits);
  const [a, b] = fixed.split('.');
  const out = a.replace(/\B(?=(\d{3})+(?!\d))/g, sep);
  return b ? `${out}.${b}` : out;
}
