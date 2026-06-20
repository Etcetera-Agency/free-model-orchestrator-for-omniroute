# Completion Review: add-pipeline-orchestration

## Summary

- Added `src/fmo/pipeline.py` with an injectable ordered `PipelineRunner`, persisted run records, per-stage status records, idempotent stage skipping before execution, fail-closed stop statuses, and deterministic exit-code mapping.
- Extended `RunRepository` to finish runs with persisted stage metadata and find prior successful stage results by idempotency key.
- Added `tests/test_pipeline.py` for run identity, ordered status recording, idempotent skips, fail-closed gating, no `/api/combos/test`, and exit-code mapping.

## Verification

- `uv run --extra test pytest -q tests/test_pipeline.py`
- `openspec validate add-pipeline-orchestration --strict`
- `uv run --extra test pytest -q tests/test_pipeline.py tests/test_spec_coverage.py`
- `openspec validate --all --strict`
- `uv run --extra test pytest -q -m 'not live'`
- `uv run --extra test pytest -q`
- `uv run --extra test pytest -q tests/test_pipeline.py tests/test_live_external_sources.py`
- `uv run --extra test pytest -q` after Code Simplifier live-helper cleanup

## Notes

- Full pytest initially failed because the live Artificial Analysis endpoint
  returned HTTP 429. Updated the live-test skip helper to treat 429 as transient
  external unavailability; rerun passed with 229 passed and 1 skipped.
