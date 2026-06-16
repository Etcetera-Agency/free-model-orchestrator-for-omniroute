# add-allocation

## Why

This phase turns scores and quota into the actual per-role combos: forecast real
demand, allocate scarce free capacity globally so roles do not silently compete
for one pool, build one broad priority combo per role, and apply the minimal diff
to OmniRoute with snapshot, smoke test and rollback. Source:
`reference/docs/modules/21,10,11,12`, `reference/docs/architecture/05`.

## What Changes

- Add `demand-forecast`: aggregate agent+dependency demand per reset horizon,
  expected vs protected, one-time 20% historical reserve, cold start.
- Add `allocator`: global allocation, hard constraints, oversubscription gate,
  one priority combo per role (no weights), degraded modes, stability.
- Add `combo-applier`: manage only `fmo-` combos, transactional apply + smoke
  test, rollback, drift protection, anti-churn.
- Add `audit-rollback`: sync runs, change log, explainability, rollback scopes,
  retention.

## Impact

- New specs: `demand-forecast`, `allocator`, `combo-applier`, `audit-rollback`.
- Depends on: all earlier phases.
- Produces the applied OmniRoute combos consumed by Hermes.
