# Change: Make stage success prove a real domain effect

## Why

Review of the composed runtime found that all canonical domain stages
(`model-matching`, `quota-research`, `access-classification`, `probing`,
`telemetry-sync`, `quota-sync`, `role-scoring`, `allocation`, `diff`, `apply`,
`audit`) are wired to a single catch-all adapter, `_domain_stage_adapter` in
`src/fmo/composition.py`, that returns `StageResult(status="success")` without
calling any domain module. None of `matcher`, `quota_research`, `access`,
`probes`, `telemetry`, `quota_manager`, `scoring`, `allocation`, `applier`, or
`audit` is imported by production code — they exist only in unit tests.

The prior change `wire-production-stage-modules` was archived as complete with
tasks 2.3/2.4 ("replace placeholder quota/access/probe/.../allocation/diff/
apply/audit stages with adapters around existing modules") checked, but the
shipped code is a no-op. It passed because the `pipeline-orchestration` scenario
"Full run calls production adapters" only asserts that *an adapter is invoked*,
not that the adapter produced its declared effect. A single shared
fabricated-success adapter satisfies that scenario.

This is the keystone fix: the spec and the executable suite must make
fabricated stage success impossible, so the remaining wiring slices have a real
red bar to turn green.

## What Changes

- Strengthen `pipeline-orchestration` so a stage's `success` is only valid when
  the stage produced its declared, observable effect (a repository write, an
  OmniRoute call, or an explicit no-change idempotency decision). A stage that
  returns `success` without its effect SHALL fail the executable suite.
- Remove the catch-all `_domain_stage_adapter` shared success helper. Replace it
  with explicit per-stage adapter dispatch. Any canonical stage not yet wired to
  its real module SHALL return a non-success `not_implemented` status (fail
  closed), never fabricated success.
- Add a reusable executable effect-assertion harness in tests that drives a
  composed `full` run against a real ephemeral Postgres and asserts each wired
  stage's side effect; the harness fails if a stage is swapped for an
  unconditional-success helper.
- Because most stages are not yet wired, `full` now stops at the first
  unwired stage with a non-success exit. Subsequent slices
  (`wire-matching-access-stages`, `wire-probe-telemetry-stages`,
  `wire-scoring-allocation-stages`, `wire-apply-audit-stages`) move the boundary
  forward one stage group at a time until `full` runs end to end.

## Impact

- Affected specs: `pipeline-orchestration`.
- Affected code: `src/fmo/composition.py`, `src/fmo/pipeline.py` (status
  vocabulary if needed), `tests/test_composition.py`, `tests/test_pipeline.py`,
  new `tests/_stage_effects.py` harness.
- Behavior: `full` and unwired single-stage commands change from a green no-op to
  a fail-closed non-success until their slice lands. This is intended: the
  service is pre-deployment on the `implement-free-model-orchestrator-changes`
  branch and must not report success without doing work.
- No new external service contract.
