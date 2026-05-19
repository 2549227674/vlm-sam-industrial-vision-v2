// stats.ts — aligned with docs/API_CONTRACT.md §6 (Phase 4.0+)

export interface AbMetrics {
  count: number;
  json_ok_rate: number;
  avg_ttft_ms: number;
  avg_decode_tps: number;
  avg_rss_mb: number;
  avg_prompt_tokens: number;
  avg_output_tokens: number;
}

// VariantMetrics for mock-data.ts buildStats() internal accumulation.
export interface VariantMetrics extends AbMetrics {
  json_ok: number;
  ttft: number;
  tps: number;
  rss: number;
  prompt: number;
  output: number;
}

export interface DashboardStatsLike {
  total: number;
  by_category: Record<string, number>;
  by_severity: Record<string, number>;
  ab_compare: Record<string, AbMetrics>;

  // Phase 4.0 backend additions; mock fallback can also provide.
  today_defects?: number;
  today_high?: number;

  // Real API provides; mock fallback may omit — components must use optional chaining.
  timeline?: Array<{ ts: string; count: number }>;
  avg_pipeline_ms?: {
    efficientad: number;
    fastsam: number;
    qwen3vl: number;
  };
  category_severity_matrix?: Record<string, Record<string, number>>;
}

export interface StatsResponse extends DashboardStatsLike {
  today_defects: number;
  today_high: number;
  timeline: Array<{ ts: string; count: number }>;
  avg_pipeline_ms: {
    efficientad: number;
    fastsam: number;
    qwen3vl: number;
  };
  category_severity_matrix: Record<string, Record<string, number>>;
  ab_compare: Record<string, AbMetrics>;
}
