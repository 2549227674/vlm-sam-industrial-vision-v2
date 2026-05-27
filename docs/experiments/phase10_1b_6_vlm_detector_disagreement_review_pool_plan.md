# Phase 10.1b-6: VLM-Detector Disagreement Review Pool Plan

**Status:** Design plan only — no implementation in this phase
**Branch:** `phase10.1b/vlm-detector-disagreement-review-pool-plan`
**Date:** 2026-05-27

---

## 1. Purpose

Design a future review pool where EdgeVLM can flag possible disagreement with
detector/localizer outputs.

**Core principle:**

- VLM may question.
- VLM must not decide.
- Frontend may show suspicious/review-needed state.
- Backend must not automatically modify canonical detection fields.

The review pool exists to surface human-review opportunities, not to automate
corrections.

---

## 2. Relationship to Current Pipeline

Current Phase 10.1b enrichment flow:

```
RK3588 / YOLO / ORT
  -> bbox, category, defect_type, confidence, anomaly_score

Backend enrichment worker / EdgeVLM
  -> observation, severity_reason, observation_source, accepted_box_ids

WebSocket UX
  -> pending/running/complete/rejected/failed enrichment state
```

The review pool sits above this as a **human-review UX / data-quality layer**.
It does not participate in the enrichment pipeline itself. It consumes
enrichment outputs and detector outputs to surface disagreement signals.

---

## 3. Hard Safety Boundary

### Review pool must NEVER automatically update:

| Field                     | Reason                                    |
|---------------------------|-------------------------------------------|
| `bboxes`                  | Detector localizer is canonical           |
| `category`                | Detector label is ground truth            |
| `defect_type`             | Detector label is ground truth            |
| `confidence`              | Detector score is authoritative           |
| `anomaly_score`           | EfficientAD output is authoritative       |
| `localization_source`     | Provenance field — must not be overwritten |
| `label_source`            | Provenance field — must not be overwritten |
| `masks`                   | Segmentation output is canonical          |
| `train labels`            | Human-annotated — never auto-modified     |

### Allowed review metadata only:

| Field             | Type      | Description                                 |
|-------------------|-----------|---------------------------------------------|
| `review_status`   | enum      | `open`, `reviewed`, `dismissed`             |
| `review_reasons`  | string[]  | One or more trigger codes                    |
| `review_source`   | string    | What generated the signal (e.g. `edge_vlm_consistency_check`) |
| `review_evidence` | JSON      | Snapshot of relevant fields at flag time     |
| `created_at`      | datetime  | When the review signal was created           |
| `reviewed_at`     | datetime  | When a human reviewed the item               |
| `reviewer_note`   | string    | Free-text human note                         |

---

## 4. Trigger Conditions

The following conditions are **review signals**, not automatic corrections.
Each condition means "a human should look at this" — not "the system should
change the detection."

| Code                            | Description                                                                                    |
|---------------------------------|------------------------------------------------------------------------------------------------|
| `category_mismatch`             | VLM observation conflicts with detector category                                               |
| `severity_type_inconsistent`    | VLM severity_reason does not support detector defect_type                                      |
| `bbox_not_supported`            | `accepted_box_ids` is empty when detector bbox exists                                          |
| `bbox_partial_support`          | `accepted_box_ids` only partially covers multi-box detections                                  |
| `guard_rejected`                | VLM output rejected by hallucination guard                                                     |
| `vlm_failed`                    | VLM enrichment failed (error/exception)                                                        |
| `vlm_timeout`                   | VLM enrichment timed out                                                                       |
| `defect_not_visible`            | VLM says defect is not visible / unclear / inconsistent                                        |
| `visual_evidence_mismatch`      | Category is valid but visual evidence appears mismatched                                       |
| `confidence_evidence_weak`      | Confidence is high but VLM evidence is weak                                                    |
| `repeated_invalid_json`         | Repeated invalid JSON for similar samples (systemic issue)                                     |

**Important:** These are heuristics for surfacing items to a human reviewer.
They must never be used as automatic correction triggers.

---

## 5. Two Implementation Options

### Option A — Frontend-Only Derived Suspicious Pool (Recommended First)

**How it works:**
- No database schema change.
- Derive suspicious state from existing fields at render time:
  - `enrichment_status` (rejected, failed)
  - `observation_source` (guard_rejected, etc.)
  - `accepted_box_ids` (empty vs. detector bbox count)
  - `error_message` (timeout, failure details)
  - `observation` text (keyword scan for conflict signals)

**Pros:**
- Lightweight and safe.
- No migration risk.
- Can be implemented as a filtered view in the existing dashboard.

**Cons:**
- Not persistent — review actions (dismiss/reviewed) are lost on refresh.
- Not auditable — no historical record of what was flagged and when.
- Limited queryability.

### Option B — Backend Persisted Review Queue (Later PR)

**How it works:**
- Add a `defect_reviews` table or `review_*` columns to the `defects` table.
- Backend enrichment worker (or a separate signal generator) writes review
  records when disagreement conditions are detected.
- Frontend reads from the review queue via a dedicated API endpoint.
- Review actions (dismiss, annotate) are persisted.

**Pros:**
- Auditable and queryable.
- Supports human labeling workflows.
- Can feed into a data quality loop (e.g., retraining signals).

**Cons:**
- Requires schema migration, API route, frontend tests.
- Higher implementation cost.
- Should be a separate PR after Option A is validated.

### Recommendation

**Start with Option A** unless persistence is explicitly required. Option A
provides immediate UX value with zero schema risk. Move to Option B only after
the review pool proves useful in practice.

---

## 6. Frontend UX

### "Needs Review" / "Suspicious Review Pool" Panel

A dedicated panel or tab in the dashboard that lists items flagged for review.

**Each item should display:**

```
+------------------------------------------------------------------+
| defect_id: 42                           [Needs Review] badge     |
+------------------------------------------------------------------+
| [Image Thumbnail]                                                |
+---------------------------+--------------------------------------+
| Detector Result           | VLM Result                           |
|   category: scratch       |   observation: "no visible scratch"  |
|   defect_type: scratch    |   severity_reason: "..."             |
|   confidence: 0.92        |   observation_source: edge_vlm       |
|   bbox count: 2           |   accepted_box_ids: []               |
|   localization_source: yolo|                                     |
|   label_source: detector  |                                      |
+---------------------------+--------------------------------------+
| Review Reason: bbox_not_supported                                |
| Status: [open] [reviewed] [dismissed]                            |
+------------------------------------------------------------------+
```

**UX requirements:**
- Detector and VLM results shown **side by side**.
- Visual design must **not** imply VLM overwrote detector output.
- Detector result is always shown as the canonical/primary result.
- VLM result is shown as supplementary evidence.
- Review reason code is human-readable (with tooltip for technical details).
- Status transitions: open -> reviewed, open -> dismissed.

---

## 7. WebSocket Behavior (Future)

A future WebSocket event type may carry review signals:

```json
{
  "type": "defect_review_signal",
  "defect_id": 123,
  "review_reasons": ["bbox_not_supported"],
  "source": "edge_vlm_consistency_check",
  "severity": "low|medium|high",
  "ts": "2026-05-27T12:00:00Z"
}
```

**Do not implement this now.** This is documented as a future option only.
The event type would be separate from existing `defect_update` events and would
not modify the defect record itself.

---

## 8. Data / Schema Design Notes

If persisted later, prefer a **separate `defect_reviews` table** over adding
columns to the `defects` table.

**Do not overload existing fields:**

| Field             | Must NOT become                  |
|-------------------|----------------------------------|
| `category`        | review-modified category         |
| `defect_type`     | review-modified defect type      |
| `confidence`      | review-adjusted confidence       |
| `bboxes`          | review-adjusted bboxes           |
| `enrichment_status` | review status (different concerns) |

**Review status is independent from enrichment status.** A defect can have
`enrichment_status: complete` and `review_status: open` simultaneously.
Enrichment status tracks VLM processing state; review status tracks human
review state.

**Proposed schema (future, Option B):**

```sql
CREATE TABLE defect_reviews (
    id              INTEGER PRIMARY KEY,
    defect_id       INTEGER NOT NULL REFERENCES defects(id),
    review_status   TEXT NOT NULL DEFAULT 'open',  -- open | reviewed | dismissed
    review_reasons  TEXT NOT NULL,                  -- JSON array of reason codes
    review_source   TEXT NOT NULL,                  -- signal generator identifier
    review_evidence TEXT,                            -- JSON snapshot of relevant fields
    reviewer_note   TEXT,
    created_at      DATETIME NOT NULL,
    reviewed_at     DATETIME
);
```

---

## 9. Testing Strategy for Future Implementation

### Backend tests

| Test case                                                           | Expected behavior                                    |
|---------------------------------------------------------------------|------------------------------------------------------|
| Review signal never mutates canonical fields                        | `category`, `defect_type`, `confidence`, `bboxes` unchanged |
| Guard-rejected outputs produce review signal, not correction        | `review_reasons` contains `guard_rejected`           |
| `accepted_box_ids` mismatch produces review signal                  | `review_reasons` contains `bbox_not_supported`       |
| No private paths/secrets in review evidence                         | `review_evidence` is sanitized                       |
| Review status independent from enrichment status                    | Both can be any combination                          |

### Frontend tests

| Test case                                                           | Expected behavior                                    |
|---------------------------------------------------------------------|------------------------------------------------------|
| Suspicious pool shows detector and VLM provenance                   | Both panels rendered with correct source labels      |
| Dismiss/review action does not alter canonical fields               | No PATCH/PUT to `category`, `defect_type`, etc.      |
| Rejected/failed enrichment appears as review-needed                 | Filtered into pool when configured                   |
| No bbox redraw from VLM signal                                      | Bbox overlay comes from detector only                |

---

## 10. Relationship to Phase 10.1b-5

- **Phase 10.1b-5 live soak should not implement the review pool.** Live soak
  is focused on enrichment pipeline stability and provider validation.
- **Live soak may collect observations** that inform the review pool design.
  For example, if live soak reveals common disagreement patterns, those patterns
  become review trigger candidates.
- **Review pool should be a follow-up** after the real EdgeVLM provider is
  connected and enrichment outputs are validated in production conditions.

---

## 11. Out of Scope

This plan explicitly does **not** include:

- No code changes (frontend, backend, or edge)
- No schema changes or migrations
- No automatic label correction
- No automatic bbox correction
- No automatic confidence adjustment
- No training label generation
- No mask correction
- No category expansion
- No live soak execution
- No deployment
- No snapshot capture
- No new API routes
- No WebSocket event type changes
- No worker/provider behavior changes

---

## 12. Security / Privacy

Review evidence must **not** contain:

| Prohibited content      | Reason                          |
|-------------------------|---------------------------------|
| Private file paths      | May expose server structure     |
| Raw IP addresses        | May expose infrastructure       |
| Tokens                  | Credential leak                 |
| Passwords               | Credential leak                 |
| API keys                | Credential leak                 |
| `EDGE_VLM_COMMAND`      | May expose model invocation     |
| Model file paths        | May expose deployment details   |
| Stack traces            | May expose internal implementation |

All `review_evidence` payloads must be sanitized before storage or transmission.

---

## 13. Recommendation: Staged Implementation

| Phase        | Scope                                      | Effort   | Risk   |
|--------------|--------------------------------------------|----------|--------|
| 10.1b-6a     | Docs-only review pool plan (this document) | Minimal  | None   |
| 10.1b-6b     | Frontend-only derived suspicious pool      | Small    | Low    |
| 10.1b-6c     | Optional persisted backend review queue    | Medium   | Medium |

**Phase 10.1b-6a** (this phase): Document the design, get alignment on
trigger conditions and safety boundaries.

**Phase 10.1b-6b**: Implement a filtered view in the frontend that derives
suspicious state from existing enrichment fields. No backend changes needed.

**Phase 10.1b-6c**: If the review pool proves valuable, add a persisted
`defect_reviews` table and a dedicated API endpoint. This should be a
separate PR with full test coverage.

---

## Appendix: Review Reason Code Reference

| Code                          | Trigger condition                                       | Severity suggestion |
|-------------------------------|---------------------------------------------------------|---------------------|
| `category_mismatch`           | VLM category != detector category                       | high                |
| `severity_type_inconsistent`  | VLM severity_reason contradicts detector defect_type    | medium              |
| `bbox_not_supported`          | `accepted_box_ids` empty, detector has bboxes           | high                |
| `bbox_partial_support`        | `accepted_box_ids` covers fewer boxes than detector     | medium              |
| `guard_rejected`              | Hallucination guard rejected VLM output                 | high                |
| `vlm_failed`                  | VLM enrichment returned error                           | low                 |
| `vlm_timeout`                 | VLM enrichment exceeded timeout threshold               | low                 |
| `defect_not_visible`          | VLM observation says defect not visible/unclear         | medium              |
| `visual_evidence_mismatch`    | Category valid but visual evidence seems wrong          | medium              |
| `confidence_evidence_weak`    | High detector confidence but weak VLM evidence          | medium              |
| `repeated_invalid_json`       | Multiple invalid JSON outputs for similar samples       | low                 |

Severity suggestions are starting points for UX prioritization, not hard rules.
