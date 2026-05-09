export interface BBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface VlmMetrics {
  ttft_ms: number;
  decode_tps: number;
  prompt_tokens: number;
  output_tokens: number;
  rss_mb: number;
  json_parse_ok: boolean;
}

export interface TraceEvent {
  name: string;
  ts: number;
  dur: number;
  tid: string;
  ph: "X";
}

export interface DefectRead {
  id: number;
  image_url: string;
  line_id: string;
  category: string;
  defect_type: string;
  severity: "low" | "medium" | "high";
  confidence: number;
  anomaly_score: number;
  bboxes: BBox[];
  description: string;
  variant: "A" | "B";
  edge_ts: string;
  pipeline_ms: {
    efficientad: number;
    fastsam: number;
    qwen3vl: number;
  };
  vlm_metrics?: VlmMetrics;
  trace_events?: TraceEvent[];
  schema_version: "v1";
  server_ts: string;
}
