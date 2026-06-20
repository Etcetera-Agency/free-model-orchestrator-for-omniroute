# Implementation Tasks

## 1. TDD Coverage

- [x] 1.1 Add a failing test proving a stage adapter that returns
  `StageResult(status="success")` without producing its declared effect fails
  the suite (effect-assertion harness in `tests/_stage_effects.py`).
- [x] 1.2 Add a failing test proving the catch-all `_domain_stage_adapter`
  shared success helper no longer exists and cannot be the configured
  `StageAdapters.domain_stage`.
- [x] 1.3 Add a failing test proving an unwired canonical stage returns the
  `not_implemented` non-success status and that `full` stops at it with a
  non-success exit code (no fabricated downstream success).
- [x] 1.4 Bind the strengthened scenarios with `@pytest.mark.spec(...)` and add
  the new scenario ids to `tests/spec_coverage_pending.txt` only until their
  tests land in this slice.

## 2. Implementation

- [x] 2.1 Replace `StageAdapters.domain_stage` single catch-all with an explicit
  per-stage adapter registry keyed by canonical stage name.
- [x] 2.2 Default every not-yet-wired canonical stage to a `not_implemented`
  adapter that returns a non-success `StageResult` (fail closed); delete
  `_domain_stage_adapter`.
- [x] 2.3 Define the "declared effect" contract per stage (repository write,
  OmniRoute call, or explicit idempotent no-change) and expose it to the test
  harness without leaking test-only hooks into production control flow.
- [x] 2.4 Ensure `_run_type`/exit-code mapping surfaces the non-success status of
  an unwired stage through the CLI (`not_implemented` → a fail-closed exit code).

## 3. Verification

- [x] 3.1 Run `tests/test_composition.py`, `tests/test_pipeline.py`,
  `tests/test_cli.py`, `tests/test_scheduler.py`.
- [x] 3.2 Run `.venv/bin/python -m pytest -q`.
- [x] 3.3 Run `npx --yes @fission-ai/openspec@latest validate --all --strict`.
- [x] 3.4 Use Code Simplifier on the new composition/test code before finishing.
- [x] 3.5 Update `completion.review` to state the no-op was removed and the
  effect contract is enforced; record the remaining unwired stages.
