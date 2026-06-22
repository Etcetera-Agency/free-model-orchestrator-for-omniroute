# Backlog

Lower-priority / not-yet-scheduled findings from the 2026-06-23 implementation
review. Items here are acknowledged but not turned into active OpenSpec slices
yet. Promote an item by opening a `openspec/changes/<id>/` proposal.

## 1. access-classification fabricates `remaining` and `reset_at`

> **Status:** the apply-gate teeth (require a positive safety-buffer floor and
> live-observed remaining; reject assumed evidence) are now scoped into the
> `harden-pipeline-resilience` slice (`combo-applier` delta). The
> fabrication-at-classification background below stays here for context.


`_access_classification_stage` (`src/fmo/composition_stages.py:602`) builds quota
evidence with `"remaining": limit` (assumes full quota remaining) and
`reset_at = now + 1 day` (synthetic). These are not observed values. For free
endpoints whose account is **absent** from `GET /api/usage/quota`, `_quota_sync_stage`
skips them (`src/fmo/composition_stages.py:855`) and never overwrites the
fabricated values, so the assumed full-remaining + future reset survive to apply.

**Why it mostly does not bite today:** the pipeline stops on `partial_stale`, and
in practice live quota-sync covers the accounts we apply against, so fabricated
rows rarely reach apply unchallenged.

**The real teeth — apply gate accepts weak evidence.**
`_endpoint_quota_row_is_safe` (`src/fmo/composition_stages.py:1671`) passes when:

- `remaining > safety_buffer` — but `safety_buffer` is read from `evidence` and
  access-classification never writes one, so the buffer is effectively `0`;
- `reset_at > now` — trivially true for the synthetic `now + 1 day`;
- `classified_at` is fresh — trivially true right after classification.

So an endpoint with **assumed** (not observed) remaining and a **zero** safety
buffer can authorize an apply. This is the part worth fixing.

**Candidate fix (scope into a slice — see note below):**
- require a configured minimum safety buffer at the apply gate (no implicit `0`);
- distinguish observed vs assumed remaining (e.g. an evidence flag) and require
  live-observed remaining at the apply gate, so assumed-equal-to-limit evidence
  cannot authorize apply.

> The apply must genuinely stay fail-closed on weak/assumed evidence. This is a
> companion to `harden-pipeline-resilience` (which lets the run continue past
> staleness and explicitly relies on apply excluding non-fresh evidence).

## 2. `hard_stop_capable` is a research claim, not verified behavior

`hard_stop_capable` flows from `research_quota_rule` (LLM/summary research, capped
at `summary_confidence_cap=0.70`, `src/fmo/composition_stages.py:399`) into the
quota rule and into the apply safety gate. No probe verifies the provider actually
hard-stops at the limit. The README/specs phrase this as "confirmed hard-stop
behavior", which overstates a researched claim.

**Priority:** low. This is a "claimed vs confirmed" semantic gap rather than an
active safety hole — the value is still gated by the deterministic confidence cap
and treated as opportunistic capacity. Revisit if/when we gain a way to observe
real hard-stop behavior (e.g. a controlled over-limit probe), or soften the doc
wording to "researched" instead of "confirmed".
