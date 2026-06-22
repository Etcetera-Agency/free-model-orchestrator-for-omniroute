# Change: Keep the daily run alive past recoverable staleness and per-endpoint errors

## Why

The once-a-day pipeline is brittle: a single recoverable hiccup aborts the whole
reconcile and skips apply for that day, with no degraded path.

- `partial_stale` is in `STOP_STATUSES` (`src/fmo/pipeline.py:41`), so any stage
  returning partial/stale — e.g. `quota-sync` on a transient `QuotaFetchError`
  (`src/fmo/composition_stages.py:840`) — stops the run before scoring,
  allocation, and apply. One flaky upstream call blocks the entire day's
  reconcile.
- `_quota_research_stage` aborts the whole stage on the FIRST endpoint error
  (`src/fmo/composition_stages.py:408`): one bad endpoint stops quota research for
  every other endpoint, again halting the run.

The fix is to continue running all stages, accumulate `partial_stale` into the
run outcome (exit 2), and keep apply fail-closed by evidence freshness so
continuing past staleness never relaxes the capacity invariant.

## What Changes

- `partial_stale` no longer aborts the run. All stages still run; partial/stale
  output is not consumed by dependents, and the run reports the most severe
  outcome (exit 2 when only staleness occurred). Hard failures
  (`validation_failed`, `external_dependency_failed`, `not_implemented`,
  `unsafe_to_apply`, apply/rollback failures) still stop or gate apply.
- Apply continues to exclude endpoints lacking fresh (non-stale) quota+probe
  evidence, so a stale upstream simply yields a smaller safe combo, never an
  unsafe one. (Freshness gating already lives in `combo-applier`.)
- `quota-research` degrades per endpoint: a single endpoint's research error is
  recorded and skipped; remaining endpoints are still researched; the stage
  reports `partial_stale` rather than failing the whole run.
- **Companion safety hardening (required for the above to be safe):** the apply
  gate stops accepting weak/assumed evidence. `_endpoint_quota_row_is_safe`
  (`src/fmo/composition_stages.py:1671`) currently passes when `safety_buffer`
  is an implicit `0` (access-classification never writes one) and when
  `remaining` is the assumed full-limit value synthesized at classification
  (`src/fmo/composition_stages.py:602`). The gate SHALL require a configured
  positive safety buffer and a live-observed remaining; assumed remaining and a
  zero buffer SHALL NOT authorize apply. (Tracked from `backlog.md` item 1.)

## Impact

- Affected specs: `pipeline-orchestration`, `quota-research`, `combo-applier`
- Affected code: `src/fmo/pipeline.py` (`STOP_STATUSES`), `src/fmo/composition_stages.py`
  (`_quota_research_stage`, `_endpoint_quota_row_is_safe`, access-classification
  evidence shape), `src/fmo/config.py` (minimum safety-buffer floor),
  pipeline-resilience, quota-research, and apply-gate tests.
