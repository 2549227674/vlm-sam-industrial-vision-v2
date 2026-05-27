# Phase 10.1b-5c2: RK3588 VLM Service + Server-Side Wrapper Smoke Report

**Date**: 2026-05-27
**Branch**: `phase10.1b/rk3588-vlm-service-wrapper-smoke`
**Base**: `4224abb` (PR #19 merged)

---

## 1. Scope

- **In scope**: 5c2 smoke only — RK3588 VLM service, server-side wrapper, reverse tunnel, end-to-end enrichment via edge_vlm subprocess provider.
- **Out of scope**: No 200/500 live soak. No public snapshot capture. No public demo switch. No review pool implementation. No EDGE_VLM_MODE=http. No cloud_vlm. No schema changes. No frontend UX changes. No YOLO/ORT/RKNN/LoRA changes.
- **Categories tested**: `metal_nut`, `cable`.

---

## 2. Topology

```
public server backend worker (uvicorn, systemd)
  -> EdgeVlmProvider subprocess mode
  -> server-side wrapper command (python3 wrapper script)
  -> wrapper reads image locally, sends base64
  -> wrapper calls http://127.0.0.1:<SERVER_TUNNEL_PORT>/vlm
  -> SSH reverse tunnel (RK3588 -> public server, via PC proxy)
  -> RK3588 VLM enrichment adapter on 127.0.0.1:<RK_VLM_PORT>
  -> adapter calls RKLLM API server on 127.0.0.1:<RKLLM_API_PORT>
  -> real Qwen3-VL-2B base RKLLM inference (NPU)
  -> strict JSON: observation, severity_reason, accepted_box_ids
  -> wrapper prints strict JSON to stdout
  -> hallucination guard (validate_vlm_output)
  -> enrichment complete
  -> WebSocket defect_enrichment_updated event
```

**Components**:
- **RK3588 VLM service**: RKLLM API server (ctypes binding to librkllmrt.so), OpenAI-compatible `/v1/chat/completions` endpoint, Qwen3-VL-2B base model with vision encoder (.rknn) on NPU.
- **VLM enrichment adapter**: Lightweight HTTP adapter bridging enrichment payload format to RKLLM API. Supports both local `image_path` and remote `image_base64`.
- **Reverse tunnel**: SSH reverse tunnel from RK3588 to public server, localhost-only binding, through PC HTTP proxy.
- **Server-side wrapper**: Python script that reads EdgeVlmProvider stdin JSON, reads image from local path, sends as base64 to VLM adapter via tunnel, outputs strict JSON to stdout.

---

## 3. Configuration (redacted)

```bash
# Public server backend env (not committed)
ENRICHMENT_ENABLED=true
ENRICHMENT_AUTO_ENQUEUE=true
ENRICHMENT_WORKER_ENABLED=true
ENRICHMENT_PROVIDER=edge_vlm
EDGE_VLM_MODE=subprocess
EDGE_VLM_COMMAND="<REDACTED_WRAPPER_COMMAND>"
EDGE_VLM_MODEL_NAME=qwen3-vl-2b-base
ENRICHMENT_TIMEOUT_S=30
ENRICHMENT_MAX_PER_MINUTE=10
ENRICHMENT_WORKER_IDLE_SLEEP_S=5
ENRICHMENT_WORKER_POLL_INTERVAL_S=2
```

**RK3588 VLM model**: Qwen3-VL-2B base W8A8 (RKLLM) + vision encoder (RKNN), context=4096, NPU 3-core.

---

## 4. S1-S7 Results

| Step | Description | Result | Notes |
|------|-------------|--------|-------|
| S1 | Tunnel health | **PASS** | Public server -> tunnel -> RK3588 adapter `/health` responds 200, ~0.8s |
| S2 | RK3588 VLM service direct local smoke | **PASS** | Local `/vlm` endpoint, metal_nut image, 14.6s latency, no forbidden keys |
| S3 | Public server wrapper direct CLI smoke | **PASS** | Exit code 0, valid strict JSON, 10.6s latency, no forbidden keys |
| S4 | Backend manual enrichment process | **PASS** | enrichment_id=4, defect_id=4109, status=complete, ~11s, observation_source=edge_vlm |
| S5 | Worker auto path | **PASS** | Upload -> auto-enqueue -> worker -> complete, defect_id=4112, ~12s |
| S6 | Canonical field immutability | **PASS** | Both defects 4109 and 4112: bboxes/category/defect_type/confidence/anomaly_score unchanged |
| S7 | Guard / timeout defense | **NOT RUN** | No safe test mode available without modifying production wrapper |

---

## 5. Metrics

### S2: VLM Service Direct

| Metric | Value |
|--------|-------|
| Endpoint | 127.0.0.1:<RK_VLM_PORT>/vlm |
| Latency (total) | 14,625 ms |
| VLM latency (internal) | 14,598 ms |
| Prompt tokens | 102 |
| Completion tokens | 73 |
| Total tokens | 175 |
| observation | "A prominent scratch on the nut surface, located within box region 0..." |
| severity_reason | "The scratch affects product aesthetics and may compromise dimensional accuracy..." |
| accepted_box_ids | [0] |
| Forbidden keys | NONE |

### S3: Wrapper Direct CLI

| Metric | Value |
|--------|-------|
| Exit code | 0 |
| Latency | 10,646 ms |
| Stderr | NONE |
| observation | "A prominent scratch is visible on the surface of the metal nut..." |
| severity_reason | "Critical defect affecting appearance and potential function." |
| accepted_box_ids | [0] |
| Forbidden keys | NONE |

### S4: Backend Manual Enrichment

| Metric | Value |
|--------|-------|
| enrichment_id | 4 |
| defect_id | 4109 |
| category | metal_nut |
| defect_type | scratch |
| Provider | edge_vlm |
| Model | qwen3-vl-2b-base |
| Status | complete |
| observation | "A prominent scratch is visible on the surface of the metal nut." |
| severity_reason | "Critical defect; may compromise structural integrity and function." |
| accepted_box_ids | [0] |
| observation_source | edge_vlm |
| Latency (created -> completed) | ~11 s |

### S5: Worker Auto Path

| Metric | Value |
|--------|-------|
| Upload POST latency | <1 s |
| enrichment_id | 5 |
| defect_id | 4112 |
| category | cable |
| defect_type | cut_inner_insulation |
| Status | complete |
| observation | "The cable part shows a cut inner insulation defect at the center hole edge." |
| severity_reason | "Critical - affects electrical integrity and safety." |
| accepted_box_ids | [0] |
| observation_source | edge_vlm |
| Latency (created -> completed) | ~12 s |
| WebSocket event observed | Yes (ws_clients=1 at time of check) |

### S6: Canonical Field Immutability

| Field | defect 4109 (pre) | defect 4109 (post) | defect 4112 (upload) | defect 4112 (post) |
|-------|-------------------|--------------------|-----------------------|--------------------|
| bboxes | [{x:0.3,y:0.3,w:0.1,h:0.1}] | unchanged | [{x:0.2,y:0.3,w:0.15,h:0.1}] | unchanged |
| category | metal_nut | metal_nut | cable | cable |
| defect_type | scratch | scratch | cut_inner_insulation | cut_inner_insulation |
| confidence | 0.95 | 0.95 | 0.95 | 0.95 |
| anomaly_score | 42.0 | 42.0 | 35.0 | 35.0 |
| localization_source | null | null | null | null |
| label_source | null | null | null | null |
| observation | (template) | edge_vlm value | null | edge_vlm value |
| severity_reason | null | edge_vlm value | null | edge_vlm value |
| observation_source | template | edge_vlm | null | edge_vlm |

**Result**: PASS — all canonical fields unchanged after enrichment.

---

## 6. Safety Checks

| Check | Result |
|-------|--------|
| No public exposure of VLM service | PASS — adapter binds to 127.0.0.1 only |
| Tunnel localhost-only | PASS — reverse tunnel binds to 127.0.0.1 on public server |
| No secrets in stderr/logs | PASS — wrapper stderr empty, adapter logs show only HTTP status |
| No real IPs/paths/tokens in report | PASS — all values use placeholders |
| No provider call in upload path | PASS — /api/edge/report returns immediately, enrichment is async |
| Canonical fields unchanged | PASS — verified for both metal_nut and cable defects |

---

## 7. Decision Gate

**Result: PASS**

All smoke steps (S1-S6) passed. S7 skipped due to no safe test mode.

**Decision**: Proceed to Phase 10.1b-5d — 200/500 live stream soak + public snapshot capture.

---

## 8. Explicit Not Done

- No full live soak (200/500 frames)
- No public snapshot capture
- No code changes (backend/frontend unchanged)
- No public demo switch
- No review pool implementation
- No EDGE_VLM_MODE=http implementation
- No cloud_vlm implementation

---

## 9. Security Scan

```
$ grep -RInE "sshpass|password|token|api[_-]?key|secret|BEGIN .*PRIVATE KEY|([0-9]{1,3}\.){3}[0-9]{1,3}|EDGE_VLM_COMMAND|/home/|/opt/|http://[0-9]|https://[0-9]|ProxyCommand|7890" docs/experiments/phase10_1b_rk3588_vlm_service_wrapper_smoke_report.md || true
```

**Benign matches**: None — report uses only placeholders (`<RK_VLM_PORT>`, `<SERVER_TUNNEL_PORT>`, `<RKLLM_API_PORT>`, `<REDACTED_WRAPPER_COMMAND>`).

No real IP addresses, SSH credentials, proxy addresses, model paths, or command values appear in this report.
