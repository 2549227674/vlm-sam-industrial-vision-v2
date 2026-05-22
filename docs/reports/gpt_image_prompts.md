# GPT Image Prompts — Concept Illustrations for Edge Deployment Summary

> These prompts generate **concept diagrams only**. Data charts (AUROC, runtime, beat sweep, LoRA collapse) must always be generated from CSV/Markdown source of truth via pandas + matplotlib.
>
> Color palette: background `#0a0c10`, cyan `#5ad6ff`, green `#4ade80`, amber `#fbbf24`, red `#f87171`.
> Style: dark industrial dashboard style, clean vector diagram, no 3D, no photo-realism.

---

## Prompt 1: RK3588 Edge-to-Cloud Industrial Vision System

**Suggested filename**: `cover_edge_cloud_system.png`

**Aspect ratio**: 21:9

```text
Create a wide dark industrial dashboard-style diagram on a solid #0a0c10 background. Clean flat vector illustration, no 3D, no photo-realism, no watermark.

Left section: a rounded rectangle labeled "RK3588 Edge (16 GB)" in cyan #5ad6ff outline. Inside it, show four vertical blocks connected top-to-bottom by green #4ade80 downward arrows: "T1 Capture" → "T2 EfficientAD-S" → "T3 FastSAM + Qwen3-VL" → "T4 Upload". Between each block, draw a small queue icon labeled "Q1", "Q2", "Q3" in amber #fbbf24. Below the blocks, a label reads "C++ · librknnrt · librkllmrt · libcurl" in dim white.

Center: a bold green #4ade80 arrow pointing right, labeled "HTTP multipart POST /api/edge/report". Below the arrow, a small red #f87171 dashed line with label "exponential backoff retry (5×)".

Middle section: a rounded rectangle labeled "FastAPI Backend" in cyan #5ad6ff outline. Inside, three blocks: "Ingestion + Validation", "SQLite WAL + Static Files", "WebSocket /ws/dashboard". A thin amber #fbbf24 arrow points down from WebSocket.

Right section: a rounded rectangle labeled "Next.js Dashboard" in cyan #5ad6ff outline. Inside, three panels: "Realtime DataTable", "Profile Trace Timeline", "AB Matrix". A thin amber #fbbf24 arrow connects from WebSocket to the dashboard.

All text in English. Labels must be crisp and readable at 1080p. No fake metrics, no random text, no extra components. Arrows flow left to right.
```

---

## Prompt 2: C++ Four-Thread Pipeline on RK3588

**Suggested filename**: `cover_four_thread_pipeline.png`

**Aspect ratio**: 16:9

```text
Create a dark industrial dashboard-style flowchart on a solid #0a0c10 background. Clean flat vector illustration, no 3D, no photo-realism, no watermark.

Draw four large rounded rectangles in a horizontal row, each representing a thread:

1. "T1 Capture" (cyan #5ad6ff border) — icon of a camera sensor. Label below: "V4L2 dma_buf / Image Loop".
2. "T2 EfficientAD-S" (cyan #5ad6ff border) — icon of a gauge. Label below: "RKNN FP16 · raw_score gate".
3. "T3 FastSAM + Qwen3-VL" (cyan #5ad6ff border) — icon of a brain/chip. Label below: "bbox cleanup · compact JSON".
4. "T4 Upload" (cyan #5ad6ff border) — icon of a cloud with arrow. Label below: "libcurl multipart".

Between T1→T2, draw a green #4ade80 queue box labeled "Q1 cap=4" with small text "drop-oldest" in dim white. Between T2→T3, draw an amber #fbbf24 queue box labeled "Q2 cap=2" with "drop-oldest". Between T3→T4, draw a green #4ade80 queue box labeled "Q3 cap=4" with "drop-oldest".

Above T2, a small red #f87171 badge reads "gate_mode: threshold | pass_all". Above T3, a small amber #fbbf24 badge reads "VLM ~10.7 s per frame".

All arrows flow left to right. All text in English. No fake metrics, no random text, no extra components, no watermark.
```

---

## Prompt 3: EfficientAD → FastSAM → Qwen3-VL Three-Stage Inference

**Suggested filename**: `cover_three_stage_inference.png`

**Aspect ratio**: 21:9

```text
Create a wide dark industrial dashboard-style diagram on a solid #0a0c10 background. Clean flat vector illustration, no 3D, no photo-realism, no watermark.

Show three large stages arranged left to right, connected by bold green #4ade80 arrows:

Stage 1 (left): A cyan #5ad6ff rounded rectangle labeled "Stage 1: EfficientAD-S". Inside: "256×256 RGB input" at top, a small grid icon representing anomaly map in the center, "raw_score (ReduceMax)" at bottom. Below the box: "FP16 RKNN · ~350 ms · 15-class per-category threshold".

Stage 2 (middle): A cyan #5ad6ff rounded rectangle labeled "Stage 2: FastSAM-s". Inside: "640×640 input" at top, a small bounding-box overlay icon in the center, "bbox proposals (5-level cleanup)" at bottom. Below the box: "FP16 RKNN · ~250 ms · clamp → area filter → IoU dedup → count limit".

Stage 3 (right): A cyan #5ad6ff rounded rectangle labeled "Stage 3: Qwen3-VL-2B". Inside: "448×448 vision + prompt" at top, a JSON icon in the center, "structured JSON output" at bottom. Below the box: "W8A8 RKLLM · ~10.7 s · TTFT ~2.2 s · decode ~10 tok/s".

A red #f87171 dashed line with label "gate: score > threshold → trigger T3" connects Stage 1 output to Stage 2 input. Below the entire diagram, a dim white label reads "Single frame latency: T2 + T3 + T4 ≈ 12 s · RSS ≈ 3.3 GB".

All text in English. No fake metrics, no random text, no extra components, no watermark.
```

---

## Prompt 4: LoRA W8A8 Quantization Collapse

**Suggested filename**: `cover_lora_w8a8_collapse.png`

**Aspect ratio**: 16:9

```text
Create a dark industrial dashboard-style comparison diagram on a solid #0a0c10 background. Clean flat vector illustration, no 3D, no photo-realism, no watermark.

Split into two columns with a vertical divider:

Left column header: "PC bf16 LoRA (rank=32)" in green #4ade80. Below, show a horizontal bar chart with two green bars:
- "defect_type_exact: 51.8%" — bar fills about half the width
- "category_exact: 95.1%" — bar fills nearly full width
A small green #4ade80 checkmark icon beside each bar. Label at bottom: "LoRA delta weights preserved at bf16 resolution".

Right column header: "RK3588 W8A8 LoRA (rank=32)" in red #f87171. Below, show a horizontal bar chart:
- "defect_type_exact: 0%" — bar is empty, red #f87171 X icon
- "category_exact: ~93%" — bar fills nearly full width, amber #fbbf24 checkmark
Label at bottom: "W8A8 quantization destroys low-magnitude delta weights".

Center divider area: a large red #f87171 arrow pointing from left (green) to right (red) with label "RKLLM W8A8 convert". Below the arrow, text in amber #fbbf24: "quantization step = max(|W|)/127 — insufficient resolution for rank-32 delta".

At the very bottom, a dim white conclusion line: "Root cause: hardware quantization constraint, not training or merge failure".

All text in English. No fake metrics, no random text, no extra components, no watermark.
```

---

## Prompt 5: beat_ms Queue Backpressure Mechanism

**Suggested filename**: `cover_beat_backpressure.png`

**Aspect ratio**: 16:9

```text
Create a dark industrial dashboard-style diagram on a solid #0a0c10 background. Clean flat vector illustration, no 3D, no photo-realism, no watermark.

Top section: a horizontal axis labeled "beat_ms (capture interval)" from left (5000 ms) to right (15000 ms) in dim white. Above the axis, draw three zones as colored horizontal bands:
- Left zone (5000–8000 ms): red #f87171 background, label "UNSTABLE · queue_drop > 0 · VLM_avg/beat > 1.4"
- Middle zone (8000–13000 ms): amber #fbbf24 background, label "BORDERLINE · queue_drop ≈ 0–1 · ratio ≈ 1.0"
- Right zone (13000–15000 ms): green #4ade80 background, label "STABLE · queue_drop = 0 · ratio < 0.85"

Center section: a diagram showing the Q2 queue (BoundedQueue cap=2) as a small amber #fbbf24 rectangle with two slots. An arrow labeled "T2 push" enters from left (green #4ade80). An arrow labeled "T3 pop (VLM ~10.7 s)" exits to right (cyan #5ad6ff). When the queue is full, a red #f87171 arrow labeled "drop-oldest" points downward to a trash icon.

Bottom section: a formula in cyan #5ad6ff: "Safe: beat_ms > VLM_p99_latency". Below it, a formula in amber #fbbf24: "Recommended: beat_ms ≥ VLM_avg / 0.85". Below it, a dim white note: "2B base pass_all: recommended 13000 ms · 4B base: ≥ 35000 ms".

All text in English. No fake metrics, no random text, no extra components, no watermark.
```

---

## Prompt 6: Phase 1–8 Project Evolution Timeline

**Suggested filename**: `cover_project_timeline.png`

**Aspect ratio**: 21:9

```text
Create a wide dark industrial dashboard-style horizontal timeline on a solid #0a0c10 background. Clean flat vector illustration, no 3D, no photo-realism, no watermark.

Draw a horizontal timeline arrow in dim white from left to right. Place eight milestone nodes along the arrow, evenly spaced:

1. "Phase 1–2" — green #4ade80 dot. Label: "FastAPI + Simulator + Contract Tests".
2. "Phase 3" — green #4ade80 dot. Label: "Next.js Dashboard + WebSocket".
3. "Phase 4" — green #4ade80 dot. Label: "Edge-Cloud Integration PASS".
4. "Phase 5" — cyan #5ad6ff dot. Label: "EfficientAD/FastSAM/Qwen3-VL Training + LoRA".
5. "Phase 6" — cyan #5ad6ff dot. Label: "RKNN/RKLLM Model Conversion".
6. "Phase 7" — amber #fbbf24 dot. Label: "C++ Four-Thread Pipeline · True E2E PASS". A small label below: "upload_ok=24/24 · json_parse_ok=100% (24 frames)".
7. "Phase 8A–C" — amber #fbbf24 dot. Label: "Threshold Calibration · VLM A/B · Beat Sweep". A small label below: "LoRA W8A8 collapse diagnosed · 2B base selected".
8. "Phase 8D" — red #f87171 dot. Label: "Deployment Summary + Job-Facing Report".

Above the timeline, a horizontal cyan #5ad6ff bracket spans Phase 1–4 with label "Track A: Backend + Frontend + Simulator". A parallel bracket spans Phase 5–8 with label "Track B: Edge C++ + RK3588 Deployment".

Below the entire timeline, a dim white conclusion line: "8 phases · 15 MVTec AD classes · 2B/4B VLM variants · W8A8 quantization diagnosed · production mainline selected".

All text in English. No fake metrics, no random text, no extra components, no watermark.
```

---

## Usage Notes

| Prompt | Suggested filename | Target section in `edge_deployment_summary.md` |
|---|---|---|
| 1 | `cover_edge_cloud_system.png` | Cover / Section 3 header |
| 2 | `cover_four_thread_pipeline.png` | Section 4 header |
| 3 | `cover_three_stage_inference.png` | Section 5 header |
| 4 | `cover_lora_w8a8_collapse.png` | Section 7.3 header |
| 5 | `cover_beat_backpressure.png` | Section 8 header |
| 6 | `cover_project_timeline.png` | Cover / Section 2 header |

Generated images should be placed in `docs/figures/` and referenced with `![...](../figures/cover_*.png)`.

These are **concept illustrations**. All quantitative data in the report must come from CSV/Markdown sources, never from generated images.
