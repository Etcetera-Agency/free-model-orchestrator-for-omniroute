# Change: Wire demand-forecast and dynamic-role-lifecycle into production

## Why

Two deterministic modules are implemented and unit tested but unreachable in the
production pipeline:

- `src/fmo/forecast.py` — `_allocation_stage` uses `role.expected_load["requests"]`
  directly as demand instead of the forecast (aggregate demand per reset horizon,
  protected/bursty demand, one-time historical reserve, cold-start floor).
- `src/fmo/role_lifecycle.py` — role reconcile, removed-role grace/reactivation,
  and new-role bootstrap never run in production; the `roles` table is consumed
  as-is.

Without these, cold-start never gets a non-zero floor, reserves and protected
demand are ignored, and roles are not reconciled against the live registry.

This slice drives allocation demand through `forecast` and runs
`dynamic-role-lifecycle` reconciliation in the production pipeline.

## What Changes

- Compute allocation demand through `forecast` (aggregate per reset horizon,
  protected/bursty demand, one-time historical reserve, cold-start floor) and
  feed it into the existing global allocator; remove the direct
  `expected_load["requests"]` shortcut.
- Add a role-lifecycle reconciliation step that reconciles the `roles` table
  against the live registry: removed-role grace, reactivation within grace, and
  new-role bootstrap — never hardcoding roles.
- Preserve determinism and the no-paid-fallback invariant in allocation.
- Add tests covering cold-start floor, reserve-applied-once, dependency-cycle
  handling, removed-role grace, and reactivation, plus an effect test that
  allocation demand is forecast-derived.

## Impact

- Affected specs: `demand-forecast`, `dynamic-role-lifecycle`,
  `pipeline-orchestration`.
- Affected code: `src/fmo/composition.py`, `src/fmo/forecast.py`,
  `src/fmo/role_lifecycle.py`, `src/fmo/allocation.py`, `src/fmo/persistence.py`,
  `tests/`.
- Depends on: `wire-scoring-allocation-stages`. Best sequenced after
  `wire-hermes-inventory-source` so forecast consumes Hermes-derived inventory.
