# Phase 10.1b-5c: Real EdgeVLM Provider Bridge Smoke Report

> **Date**: 2026-05-27
> **Branch**: `phase10.1b/real-edge-vlm-provider-bridge-smoke`
> **Status**: **BLOCKED** — real EdgeVLM subprocess wrapper not available on public server.
> Full 200/500 live soak NOT run. Public snapshot NOT captured.

---

## 1. Scope

Phase 10.1b-5c validates one minimal real `edge_vlm` enrichment path:

```
vision.hanlab.app backend worker
  -> EdgeVlmProvider subprocess mode
  -> server-side wrapper command
  -> real VLM inference
  -> strict JSON output
  -> hallucination guard
  -> observation / severity_reason / observation_source=edge_vlm
  -> WebSocket enrichment update
  -> frontend terminal re-fetch
```

This is NOT the 200/500 live soak. This is NOT public snapshot capture.

---

## 2. Current Baseline

| Item | Value |
|---|---|
| Main commit | `fe6f47c` (PR #17 + #18 merged) |
| Server synced | Yes (after PR #17 preflight) |
| Enrichment routes | `/api/defects/{id}/enrichment`, `/api/enrich/{id}/process` |
| Worker loop | Available |
| Prior preflight provider | `template` |
| Server health | `{"status":"ok","version":"v1","uptime_s":"<redacted>"}` |
| Current `ENRICHMENT_PROVIDER` | `template` |

---

## 3. Real Provider Bridge Configuration (Redacted)

Target env vars for `edge_vlm` subprocess mode:

```
ENRICHMENT_ENABLED=true
ENRICHMENT_AUTO_ENQUEUE=true
ENRICHMENT_WORKER_ENABLED=true
ENRICHMENT_PROVIDER=edge_vlm
EDGE_VLM_MODE=subprocess
EDGE_VLM_COMMAND="<REDACTED_WRAPPER_COMMAND>"
EDGE_VLM_MODEL_NAME="<MODEL_NAME_LABEL>"
ENRICHMENT_TIMEOUT_S=30
ENRICHMENT_MAX_PER_MINUTE=10
ENRICHMENT_WORKER_IDLE_SLEEP_S=5
ENRICHMENT_WORKER_POLL_INTERVAL_S=2
```

---

## 4. Blocker Analysis

### Preflight Checks Performed

| Check | Result | Detail |
|---|---|---|
| VLM wrapper script on server | **NOT FOUND** | No shell/Python wrapper script exists in `<REMOTE_PROJECT_DIR>/` |
| VLM model files on server | **NOT FOUND** | `models/` directory does not exist on server |
| ML runtime on server | **NOT FOUND** | No torch, transformers, onnxruntime, or rknn libraries installed |
| edge_pipeline binary | **Cannot run** | Compiled x86-64 but depends on `librknnrt.so` (RKNN NPU runtime, not available on server) |
| RK3588 reachability | **UNREACHABLE** | RK3588 is on local network `192.168.x.x`; cloud server cannot reach it |
| Python VLM script | **NOT FOUND** | No VLM inference script in `scripts/` or elsewhere |

### Root Cause

The public server (`vision.hanlab.app`) is a DigitalOcean droplet (x86-64, no GPU, no NPU). It cannot run VLM inference locally because:

1. **No ML runtime**: No PyTorch, transformers, ONNX Runtime, or RKNN toolkit installed.
2. **No model files**: No `.rkllm`, `.rknn`, or `.safetensors` model files on the server.
3. **No wrapper script**: No script exists that reads stdin JSON and emits VLM output JSON.
4. **Network isolation**: The RK3588 edge device is on a local network (192.168.x.x) unreachable from the cloud server.
5. **Binary incompatibility**: The `edge_pipeline` binary requires `librknnrt.so` (RKNN NPU runtime) which only exists on ARM64 RK3588 hardware.

### What Would Be Needed

To enable real `edge_vlm` subprocess mode on the public server, one of these is required:

**Option A — Remote VLM wrapper**:
- A wrapper script on the server that SSHes/tunnels to the RK3588 and runs VLM inference remotely.
- Requires: persistent SSH tunnel or VPN between cloud server and RK3588, plus wrapper script.

**Option B — Local VLM runtime on server**:
- Install a CPU-based VLM runtime (e.g., transformers + Qwen3-VL-2B) on the server.
- Requires: ~8GB disk, ~4GB RAM, ~30s per inference (CPU-only).
- Requires: model file download and wrapper script.

**Option C — External VLM API endpoint**:
- A publicly reachable HTTP endpoint running VLM inference.
- Requires: `EDGE_VLM_MODE=http` (not yet implemented, out of scope for this PR).

**Option D — RK3588 with public IP or tunnel**:
- Expose the RK3588's VLM service to the internet via public IP, Tailscale, or Cloudflare Tunnel.
- Requires: network configuration on the edge device.

---

## 5. Smoke Scenarios

### S1 — Public Backend Health

| Item | Result |
|---|---|
| `GET /api/health` | `{"status":"ok"}` |
| **Verdict** | **PASS** |

### S2 — Wrapper Direct CLI Smoke

| Item | Result |
|---|---|
| Wrapper script | NOT FOUND |
| **Verdict** | **BLOCKED** |

### S3 — Backend Manual Enrichment Process

| Item | Result |
|---|---|
| Could not test | No real `edge_vlm` provider available |
| Template provider still works | Confirmed via PR #17 preflight |
| **Verdict** | **BLOCKED** |

### S4 — Worker Auto Path

| Item | Result |
|---|---|
| Could not test with real VLM | No wrapper available |
| Template auto-path confirmed working | PR #17 preflight (defect 4109) |
| **Verdict** | **BLOCKED** |

### S5 — Guard Defense

| Item | Result |
|---|---|
| Could not test with real VLM | No wrapper available |
| Guard code reviewed | `enrichment_guard.py` validates forbidden keys correctly |
| **Verdict** | **BLOCKED** (code review only) |

### S6 — Timeout/Error Defense

| Item | Result |
|---|---|
| Could not test with real VLM | No wrapper available |
| Error handling reviewed | `vlm_provider.py` catches `ProviderTimeoutError`, `ProviderUnavailableError`, `VlmProviderError` |
| **Verdict** | **BLOCKED** (code review only) |

---

## 6. Canonical Field Immutability

Not tested with real VLM (no wrapper available). Template provider confirmed immutable in PR #17 preflight.

---

## 7. WebSocket UX Check

Not tested with real VLM. Template provider WS events confirmed in PR #17 preflight.

---

## 8. Rollback

No rollback needed — no changes were made to the server configuration. Server remains on `ENRICHMENT_PROVIDER=template`.

---

## 9. Decision Gate

| Gate | Result |
|---|---|
| Real `edge_vlm` smoke passed | **NO — BLOCKED** |
| Blocker | Wrapper / VLM runtime / network endpoint missing |
| Can proceed to 200/500 soak | **NO** |

### Recommended Next Steps

1. **Fastest path**: Create a minimal Python wrapper script that calls a CPU-based VLM on the server (Option B). Requires installing transformers + downloading Qwen3-VL-2B (~4.5GB). Inference ~30s/image on CPU.
2. **Best path**: Expose RK3588 VLM via tunnel (Option D). Real edge inference, low latency.
3. **Deferred**: Implement `EDGE_VLM_MODE=http` (Option C). Out of scope for current PR.

---

## 10. Security Scan

```bash
grep -RInE "sshpass|password|token|api[_-]?key|secret|BEGIN .*PRIVATE KEY|([0-9]{1,3}\.){3}[0-9]{1,3}|EDGE_VLM_COMMAND|/opt/|/home/|http://[0-9]|https://[0-9]" \
  docs/experiments/phase10_1b_real_edge_vlm_provider_bridge_smoke_report.md || true
```

**Result**: No secrets, no raw private IPs, no credentials, no server filesystem paths. All values redacted with placeholders. The `192.168.x.x` reference is a generic private range notation, not a real IP.

---

## 11. Files Changed

| File | Action |
|---|---|
| `docs/experiments/phase10_1b_real_edge_vlm_provider_bridge_smoke_report.md` | Created |

No application code, config, wrapper scripts, or model files were created or modified.

---

## 12. Explicit Statements

- **Real `edge_vlm` provider bridge smoke was NOT completed** — blocker: no VLM wrapper/runtime/endpoint available on public server.
- **Full 200/500 live soak was NOT run.**
- **Public snapshot was NOT captured.**
- **No secrets or private paths were committed.**
- **No server configuration was changed.**
- **No code was modified.**
