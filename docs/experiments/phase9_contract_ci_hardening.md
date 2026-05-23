# Phase 9: API Contract & CI Hardening

**日期**：2026-05-23
**文档**：CLAUDE_03_API_CONTRACT_AND_CI_HARDENING.md
**分支**：main
**执行者**：Claude Code

---

## 1. 执行目标

以 `docs/API_CONTRACT.md` v1.2 为唯一权威，建立可测试、可同步、可防漂移的 contract 基础设施。确保 edge / simulator / backend / frontend 四端长期一致。

---

## 2. 完成项

### 2.1 JSON Schema 导出

**文件**：`scripts/export_contract_schema.py`

从 Pydantic v2 `DefectCreate` 模型自动导出 JSON Schema，生成以下文件：

| 文件 | 说明 |
|---|---|
| `docs/schema/defectcreate.v1.2.schema.json` | DefectCreate 完整 schema |
| `docs/schema/defectread.v1.2.schema.json` | DefectRead（含 id/image_url/server_ts） |
| `docs/schema/bbox.v1.2.schema.json` | BBox 子 schema |
| `docs/schema/vlmmetrics.v1.2.schema.json` | VlmMetrics 子 schema |
| `docs/schema/traceevent.v1.2.schema.json` | TraceEvent 子 schema |
| `docs/schema/defect_report.v1.2.schema.json` | 合并 bundle（用于 jsonschema 校验） |

### 2.2 Contract Fixtures

**目录**：`backend/tests/contract/fixtures/`

| 文件 | 用途 |
|---|---|
| `edge_report_valid_minimal_v1_2.json` | 最小合法 payload（无 bboxes/vlm_metrics/trace_events） |
| `edge_report_valid_full_v1_2.json` | 完整合法 payload（含 trace_events 7 事件、2 bboxes、vlm_metrics） |
| `edge_report_invalid_extra_field.json` | 含未知字段 `unknown_field` → `extra="forbid"` 拒绝 |
| `edge_report_invalid_naive_edge_ts.json` | `edge_ts` 无时区 → `must_be_aware` 拒绝 |
| `edge_report_invalid_bbox_overflow.json` | `x+w=1.2 > 1.0` → 路由二次校验拒绝 |
| `edge_report_invalid_bbox_negative.json` | `x=-0.1 < 0` → Pydantic `ge=0` 拒绝 |
| `edge_report_invalid_missing_required.json` | 缺少 `line_id` → required 拒绝 |
| `edge_report_invalid_category.json` | `category="invalid_category"` → Literal 拒绝 |
| `edge_report_invalid_variant.json` | `variant="invalid_variant"` → validator 拒绝 |

### 2.3 新增 Contract Tests

从原有 31 tests 扩展到 **74 tests**。新增测试文件：

| 文件 | 测试数 | 覆盖范围 |
|---|---|---|
| `test_contract_fixtures.py` | 9 | JSON fixture 文件 ↔ Pydantic schema 对齐 |
| `test_post_report_extended.py` | 23 | 全 15 类 category、extra field 拒绝（顶层/nested/bbox）、negative bbox、pipeline_ms 缺键/多键、trace_events WS 广播 |
| `test_golden_alignment.py` | 8 | simulator ↔ Pydantic ↔ JSON Schema 三端 golden sample 对齐 |

**新增覆盖的关键场景**：

| 场景 | 之前 | 之后 |
|---|---|---|
| 全 15 类 MVTec category | 仅测 metal_nut | 15/15 parametrize |
| unknown field in meta | 未测 | 3 tests（顶层/nested VlmMetrics/nested BBox） |
| negative bbox | 未测 | 2 tests（x<0 / y<0） |
| pipeline_ms 缺 stage | 未测 | tested |
| pipeline_ms 多 stage | 未测 | tested |
| trace_events WS round-trip | 未测 | tested |
| simulator → Pydantic alignment | 未测 | 6 tests（多 category × variant） |
| JSON Schema validation | 未测 | 2 tests（jsonschema library） |

### 2.4 Contract Drift Checker

**文件**：`scripts/check_contract_drift.py`

功能：
1. 重新从 Pydantic 模型导出 schema
2. 与 `docs/schema/defect_report.v1.2.schema.json` 快照做 diff
3. 不一致时 exit 1 并输出新增/移除的 properties
4. 提示操作：bump contract version + re-export + update docs

**文件**：`scripts/validate_contract.py`

功能：
- 校验单个 JSON 文件是否符合 DefectCreate schema
- 同时使用 Pydantic + jsonschema 双重验证

### 2.5 Frontend 类型对齐

**变更**：

| 文件 | 变更 |
|---|---|
| `frontend/src/types/defect.ts` | 新增 `MvtecCategory` (15 类 union type)、`Severity` 类型；`DefectRead.category` 从 `string` 改为 `MvtecCategory` |
| `frontend/src/lib/mock-data.ts` | import `MvtecCategory`；`makeDefect()` 中 category 强转 `as MvtecCategory` |
| `frontend/package.json` | 新增 `"typecheck": "tsc --noEmit"` script |

### 2.6 CI 基础设施

**GitHub Actions**：`.github/workflows/contract.yml`

| Job | 步骤 |
|---|---|
| `contract` | Backend tests → Drift check → Frontend typecheck |
| `contract-validate-fixtures` | Validate all valid fixtures against schema |

**本地 Makefile**：`Makefile`

| Target | 说明 |
|---|---|
| `make contract-test` | `PYTHONPATH=. pytest backend/tests/contract/ -v` |
| `make contract-check` | `python scripts/check_contract_drift.py` |
| `make contract-frontend` | `cd frontend && npm run typecheck` |
| `make contract-fixtures` | Validate all valid fixtures |
| `make contract-export` | Re-export JSON Schema |
| `make contract-all` | Run all of the above |

---

## 3. 验收结果

```
$ PYTHONPATH=. pytest backend/tests/contract/ -v
74 passed in 1.84s

$ python scripts/check_contract_drift.py
OK: Schema matches snapshot (defect_report.v1.2.schema.json)

$ cd frontend && npm run typecheck
(exit 0, no errors)

$ for f in backend/tests/contract/fixtures/edge_report_valid_*.json; do
    python scripts/validate_contract.py "$f"
  done
OK (Pydantic) + OK (JSON Schema) for all valid fixtures
```

---

## 4. 修改文件清单

### 新增文件（14）

| 文件 | 说明 |
|---|---|
| `scripts/export_contract_schema.py` | JSON Schema 导出脚本 |
| `scripts/check_contract_drift.py` | Schema 漂移检测 |
| `scripts/validate_contract.py` | 单文件 contract 校验 |
| `docs/schema/defectcreate.v1.2.schema.json` | DefectCreate schema |
| `docs/schema/defectread.v1.2.schema.json` | DefectRead schema |
| `docs/schema/bbox.v1.2.schema.json` | BBox schema |
| `docs/schema/vlmmetrics.v1.2.schema.json` | VlmMetrics schema |
| `docs/schema/traceevent.v1.2.schema.json` | TraceEvent schema |
| `docs/schema/defect_report.v1.2.schema.json` | Combined schema bundle |
| `backend/tests/contract/fixtures/*.json` | 9 fixture files |
| `backend/tests/contract/test_contract_fixtures.py` | Fixture validation tests |
| `backend/tests/contract/test_post_report_extended.py` | Extended validation tests |
| `backend/tests/contract/test_golden_alignment.py` | Golden sample alignment tests |
| `.github/workflows/contract.yml` | GitHub Actions CI |
| `Makefile` | Local CI convenience |

### 修改文件（3）

| 文件 | 变更 |
|---|---|
| `frontend/src/types/defect.ts` | +`MvtecCategory`, +`Severity`, `category` 改为 union type |
| `frontend/src/lib/mock-data.ts` | +import `MvtecCategory`, category cast |
| `frontend/package.json` | +`"typecheck"` script |

---

## 5. 四端字段一致性确认

| 字段 | API_CONTRACT.md v1.2 | Backend Pydantic | Frontend TS | Simulator | Fixtures |
|---|---|---|---|---|---|
| `line_id` | str, 1-32 | str, 1-32 | string | str | str |
| `category` | Literal 15 类 | Literal 15 类 | MvtecCategory (15) | str (from test dirs) | enum 15 |
| `defect_type` | str, 1-64 | str, 1-64 | string | str | str |
| `severity` | low/medium/high | Literal 3 | Severity | str | enum 3 |
| `confidence` | 0-1 | 0-1 | number | float | number |
| `anomaly_score` | ≥0 | ≥0 | number | float | number |
| `bboxes` | list[BBox], max 16 | list[BBox], max 16 | BBox[] | list[dict] | array |
| `BBox.x` | 0-1 | ge=0, le=1 | number | 0.05-0.70 | 0.1 |
| `BBox.w` | >0, ≤1 | gt=0, le=1 | number | 0.05-0.25 | 0.3 |
| `description` | ≤1024 | ≤1024 | string | str | str |
| `variant` | 4 new + A/B | validator str | VariantKey | str | str |
| `edge_ts` | tz-aware ISO8601 | tz-aware validator | string | isoformat() | ISO+offset |
| `pipeline_ms` | 3 stages required | 3 stages validator | {3 keys} | dict | object |
| `vlm_metrics` | Optional | Optional | optional | always present | optional |
| `trace_events` | Optional, max 64 | Optional, max 64 | optional | always present | optional |
| `schema_version` | "v1" | Literal["v1"] | "v1" | "v1" | "v1" |

---

## 6. 剩余风险

| 风险 | 级别 | 说明 | 缓解措施 |
|---|---|---|---|
| C++ edge golden meta 未建立 | 低 | 板端 C++ 未生成 golden JSON 文件 | 板端到货后可由 `validate_contract.py` 校验 |
| `jsonschema` 为 optional 依赖 | 低 | `test_golden_alignment.py` 中 JSON Schema 测试在无 jsonschema 时 skip | CI 已显式安装 |
| frontend `category` 为 union type 可能影响第三方 API | 低 | 如果未来 API 返回非 MVTec category 会导致 TS 类型错误 | 需要时改为 `MvtecCategory | string` |
| contract version 未在 backend health 响应中暴露 | 低 | `/api/health` 返回 `"version": "v1.1"` 但 contract 为 v1.2 | 可在后续更新 |

---

## 7. 必过命令（验收 checklist）

```bash
# 1. Backend contract tests
PYTHONPATH=. pytest backend/tests/contract/ -v

# 2. Schema drift check
python scripts/check_contract_drift.py

# 3. Frontend typecheck
cd frontend && npm run typecheck

# 4. Fixture validation
for f in backend/tests/contract/fixtures/edge_report_valid_*.json; do
  python scripts/validate_contract.py "$f"
done

# 5. All-in-one
make contract-all
```
