export type VariantKey =
  | "2B_base" | "2B_lora" | "4B_base" | "4B_lora"
  | "A" | "B"
  | "ort_2B" | "ort_4B";

export type MvtecCategory =
  | "bottle" | "cable" | "capsule" | "carpet" | "grid"
  | "hazelnut" | "leather" | "metal_nut" | "pill" | "screw"
  | "tile" | "toothbrush" | "transistor" | "wood" | "zipper";

export type Severity = "low" | "medium" | "high";

export type ModelSize = "2B" | "4B";
export type ModelVariant = "base" | "lora";

export interface ActiveConfig {
  model_size: ModelSize;
  variant: ModelVariant;
}

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
  cat?: string;
}

export interface DefectRead {
  id: number;
  image_url: string;
  line_id: string;
  category: MvtecCategory;
  defect_type: string;
  severity: Severity;
  confidence: number;
  anomaly_score: number;
  bboxes: BBox[];
  description: string;
  variant: VariantKey;
  edge_ts: string;
  pipeline_ms: {
    efficientad: number;
    fastsam?: number;       // v1.2 legacy
    qwen3vl?: number;       // v1.2 legacy
    localizer?: number;     // v1.3 new
    upload?: number;        // v1.3 new
    enrichment?: number;    // v1.3 new
  };
  vlm_metrics?: VlmMetrics;
  trace_events?: TraceEvent[];
  schema_version: "v1";
  server_ts: string;

  // v1.3: Phase 10 source fields
  localization_source?: string;
  label_source?: string;
  observation_source?: string;
  defect_family?: string;
  observation?: string;
  severity_reason?: string;
  object_proposals?: BBox[];
  gt_reference_bboxes?: BBox[];
}

// Phase 10.1: enrichment types

export type EnrichmentStatus =
  | "pending" | "running" | "complete" | "failed" | "rejected" | "skipped";

export type EnrichmentProvider = "template" | "edge_vlm" | "cloud_vlm";

export interface DefectEnrichmentRead {
  id: number;
  defect_id: number;
  provider: EnrichmentProvider;
  provider_model: string;
  prompt_version: string;
  status: EnrichmentStatus;
  observation?: string | null;
  severity_reason?: string | null;
  accepted_box_ids?: number[] | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}
