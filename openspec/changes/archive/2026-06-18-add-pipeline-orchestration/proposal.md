# Change: Add pipeline orchestration runner

## Why

Every pipeline module under `src/fmo/` (discovery, quota, probe, scoring,
allocation, applier, audit, rollback) is currently imported only by its own
tests — nothing chains the stages into a run. `system-architecture` and
`scheduler` specify an ordered, idempotent, fail-closed daily pipeline, but no
code realizes it. This slice adds the runner that sequences the stages through
persisted run state and maps outcomes to the deterministic exit codes.

## What Changes

- Add `src/fmo/pipeline.py`: a `PipelineRunner` that executes stages in the
  canonical order (metadata sync → discovery → match → quota research/classify →
  probe → telemetry/quota sync → score → allocate → diff → apply → audit) and
  records each stage's outcome against a persisted run record (`--run-id`).
- Honor stage idempotency keys so unchanged stages are skipped on re-run.
- Fail closed: a failed safety gate stops downstream apply; partial/stale inputs
  do not feed dependent stages.
- Map run outcomes to exit codes (0 / 2 / 3 / 4 / 5 / 6 / 7).
- Never call `/api/combos/test`.

## Impact

- Affected specs: `pipeline-orchestration` (new capability); relies on
  `system-architecture` (idempotency, forbidden transitions) and `persistence`.
- Affected code: new `src/fmo/pipeline.py`; consumes existing stage modules and
  `src/fmo/persistence.py`.
- Depends on `add-persistence-repositories`.
