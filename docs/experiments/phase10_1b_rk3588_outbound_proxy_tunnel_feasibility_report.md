# Phase 10.1b-5b: RK3588 Outbound Proxy + Reverse Tunnel Feasibility Report

> **Date**: 2026-05-27
> **Branch**: `phase10.1b/rk3588-outbound-proxy-tunnel-feasibility`
> **Status**: All feasibility checks PASS. No VLM run. No full soak. No snapshot.

---

## 1. Scope

Network feasibility smoke only:

- RK3588 -> Windows PC proxy -> public server (outbound)
- Public server -> reverse tunnel -> RK3588 test service (inbound)

No VLM inference. No 200/500 live soak. No public snapshot. No code changes.

---

## 2. Topology

```
RK3588 (<RK3588_HOST>)
  -> Ethernet
  -> Windows PC proxy <PC_ETHERNET_SHARE_IP>:7890
  -> Internet
  -> <PUBLIC_SERVER_HOST>
  -> reverse tunnel localhost:<SERVER_TUNNEL_PORT>
  -> RK3588 localhost:<RK_TEST_PORT>
```

All values below use placeholders. Real IPs, usernames, and credentials are not committed.

---

## 3. Proxy Checks

### PC Proxy Reachability from RK3588

| Item | Result |
|---|---|
| `nc -vz <PC_ETHERNET_SHARE_IP> 7890` | `Connection succeeded` |
| **Verdict** | **PASS** |

### HTTPS Through Proxy (curl -x)

| Item | Result |
|---|---|
| `curl -s -x http://<PC_ETHERNET_SHARE_IP>:7890 https://vision.hanlab.app/api/health` | `{"status":"ok"}` |
| **Verdict** | **PASS** |

### Env-Based Proxy

| Item | Result |
|---|---|
| `export http_proxy=... https_proxy=...; curl -s https://vision.hanlab.app/api/health` | `{"status":"ok"}` |
| **Verdict** | **PASS** |

---

## 4. Reverse Tunnel Checks

### Tunnel Command

SSH reverse tunnel via proxy, using `nc -X 5` (SOCKS5) as ProxyCommand. Command and credentials fully redacted.

### Tunnel Port Bind

| Item | Result |
|---|---|
| Server `ss -tlnp` for tunnel port | `LISTEN 127.0.0.1:<SERVER_TUNNEL_PORT>` |
| Bound to `0.0.0.0`? | No — `127.0.0.1` only |
| **Verdict** | **PASS** (local-only, no public exposure) |

### Server -> RK3588 Through Tunnel

| Item | Result |
|---|---|
| `curl http://127.0.0.1:<SERVER_TUNNEL_PORT>/` | `{"status":"rk3588_ok"}` |
| Response proves RK3588 test service reached | Yes |
| **Verdict** | **PASS** |

---

## 5. Security Checks

| Check | Result |
|---|---|
| No public exposure of RK3588 test service | Confirmed — tunnel bound to `127.0.0.1` only |
| No `0.0.0.0` tunnel bind | Confirmed |
| No credentials printed | Confirmed |
| No real IPs committed | Confirmed — placeholders used |
| No SSH key paths committed | Confirmed |
| No proxy credentials committed | Confirmed |
| No raw tunnel command with secrets | Confirmed — redacted |
| Tunnel and test service cleaned up after test | Confirmed — port closed |

---

## 6. Decision Gate

| Gate | Result |
|---|---|
| RK3588 can use PC proxy | **PASS** |
| RK3588 can reach public server via proxy | **PASS** |
| Reverse tunnel established | **PASS** |
| Public server can reach RK3588 test service via tunnel | **PASS** |
| Tunnel bound to localhost only | **PASS** |

**Decision**: Proceed to Phase 10.1b-5c2: RK3588 VLM service + server-side wrapper smoke.

---

## 7. Next Recommended Architecture

If tunnel feasibility passes, the future architecture is:

```
Public server:
  EDGE_VLM_MODE=subprocess
  EDGE_VLM_COMMAND="<REDACTED_WRAPPER_COMMAND>"

Wrapper:
  reads stdin JSON from EdgeVlmProvider
  calls http://127.0.0.1:<SERVER_TUNNEL_PORT>/vlm
  receives strict JSON
  prints strict JSON to stdout

RK3588:
  runs local VLM service bound to 127.0.0.1
  exposed only through reverse tunnel
```

Not implemented in this task — feasibility only.

---

## 8. Explicit Not Done

- No VLM inference
- No `edge_vlm` provider config switch
- No backend code change
- No frontend code change
- No public snapshot
- No 200/500 soak

---

## 9. Security Scan

```bash
grep -RInE "sshpass|password|token|api[_-]?key|secret|BEGIN .*PRIVATE KEY|([0-9]{1,3}\.){3}[0-9]{1,3}|/home/|/opt/|ssh -|ProxyCommand|7890" \
  docs/experiments/phase10_1b_rk3588_outbound_proxy_tunnel_feasibility_report.md || true
```

**Result**: No secrets, no real IPs, no credentials. All values are placeholders (`<PC_ETHERNET_SHARE_IP>`, `<SERVER_TUNNEL_PORT>`, `<RK_TEST_PORT>`, etc.). The port number 7890 appears only as a generic proxy port reference, not paired with any real IP.
