export interface AbMetrics {
  count: number;
  json_ok_rate: number;
  avg_ttft_ms: number;
  avg_decode_tps: number;
  avg_rss_mb: number;
  avg_prompt_tokens: number;
}

export interface StatsResponse {
  total: number;
  by_category: Record<string, number>;
  by_severity: Record<string, number>;
  timeline: Array<{ ts: string; count: number }>;
  ab_compare: {
    A: AbMetrics;
    B: AbMetrics;
  };
  avg_pipeline_ms: {
    efficientad: number;
    fastsam: number;
    qwen3vl: number;
  };
  category_severity_matrix: Record<string, Record<string, number>>;
}
