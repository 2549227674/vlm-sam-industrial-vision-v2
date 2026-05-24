# Phase 9: Public Demo Post-Deploy Seed & Hardening

**Date**: 2026-05-24
**Executed by**: Claude Code (Opus 4.7)

## 1. Public URLs

| Endpoint | URL |
|---|---|
| Frontend | https://vision.hanlab.app/ |
| API Health | https://api.vision.hanlab.app/api/health |
| API Defects | https://api.vision.hanlab.app/api/defects |
| API Stats | https://api.vision.hanlab.app/api/stats |

## 2. Snapshot Import

| Item | Value |
|---|---|
| Source | `frontend/public/demo-data/real_run_latest/` |
| Source type | `real_rk3588` |
| is_mock | `false` |
| contract_version | `v1.2` |
| Records imported | 20 |
| Images copied | 20 |
| Image dest | `/var/lib/vision-demo/static/defects/imported/phase9_soak/` |
| Categories | cable (6), capsule (9), carpet (5) |
| Severity dist | high: 2, low: 10, medium: 8 |

## 3. API Verification

| Check | Result |
|---|---|
| `/api/defects` total | 20 (PASS) |
| `/api/stats` total | 20 (PASS) |
| Image URL HTTP 200 | PASS |
| Record has `pipeline_ms` | PASS |
| Record has `vlm_metrics` | PASS |
| Record has `trace_events` | PASS |

## 4. Image URL Verification

Sample: `/static/defects/imported/phase9_soak/cb2c7b0ada5347f09a151694830b4aa5.jpg`
HTTP 200 via `https://api.vision.hanlab.app` (PASS)

## 5. Upload Auth Verification

| Test | Expected | Result |
|---|---|---|
| POST without token | 401 | 401 (PASS) |
| POST with wrong token | 401 | 401 (PASS) |

## 6. Frontend Data Source Badge

The dashboard shows `实时 RK3588 API / Live RK3588 API` with 20 records displayed.
Capability Caveats section shows bilingual (Chinese + English) caveats.

## 7. Old Copy Fixes

| File | Old | New |
|---|---|---|
| OverviewPage.tsx | Schema v1.1 | Contract v1.2 |
| OverviewPage.tsx | INT8 / W8A8 量化 | EAD/FastSAM FP16 · Qwen3-VL W8A8 |
| OverviewPage.tsx | INT8 / W8A8 量化 (badge) | EAD/FastSAM FP16, Qwen3-VL W8A8 |
| BottomBar.tsx | schema v1.1 | contract v1.2 |
| RK3588Twin.tsx | bboxes + mask | bbox proposal |
| RK3588Twin.tsx | FastSAM task: 分割掩码 | bbox 提案 |
| RK3588Twin.tsx | 640×640 · INT8 | 640×640 · FP16 |
| ModelsPage.tsx | FastSAM outputs ["masks","bboxes"], quant INT8 | outputs ["bboxes"], quant FP16 |
| ABMatrix.tsx | INT8/W8A8 (2 rows) | W8A8 |
| LogsPage.tsx | mask_area | proposal_conf |

## 8. NOPASSWD Sudo

Status: **Revoked**. The `/etc/sudoers.d/deploy` file has been removed. The `deploy` user now requires a password for sudo operations. Verified via `sudo -n true` returning "a password is required".

## 9. New Files

| File | Purpose |
|---|---|
| `scripts/import_real_run_snapshot.py` | Idempotent snapshot import script (SQLite direct) |

## 10. Release Gate Summary

| Gate | Status |
|---|---|
| SSH | PASS |
| Contract (74 tests) | PASS |
| Frontend build | PASS |
| API health | PASS |
| API defects > 0 | PASS (20) |
| API stats > 0 | PASS (20) |
| Image URL 200 | PASS |
| Frontend badge (Live) | PASS |
| Snapshot seed (real) | PASS |
| Upload auth 401 | PASS |
| No secrets in diff | PASS |
| Text polish (old copy) | PASS |
| Sudo cleanup | PASS |
| README demo link | PASS |

## 11. Remaining Risks

1. **No HTTPS for IP fallback** — `http://157.245.60.152` still serves HTTP; `.app` TLD forces HTTPS for domain access.
3. **SQLite on 1 vCPU** — adequate for demo load, not for production concurrency.
4. **Snapshot data is historical** — 20 records from Phase 9 soak test, not live RK3588 stream. Documented in manifest caveats.
5. **FastSAM mask decode** still TODO — current output is bbox proposals only.
