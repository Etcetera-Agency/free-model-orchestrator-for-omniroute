# Change: Add the FMO pool-spec publisher (additive)

## Why

First FMO slice — additive and flag-aware. Add the ability to compose Hermes roles +
demand + constraints into an `fmo-pools/v1` generation and publish it to OmniRoute,
without yet removing the old control-plane path. This lets FMO publish (shadow)
alongside the existing allocate+apply path, preserving the single-writer invariant
until the cutover.

Concept: `omniroute-pool-migration-concept/docs/FMO_SIDE_IMPLEMENTATION.md` (§5
pipeline, §6 contract, §7 band intent), `FMO_OMNIROUTE_POOL_BALANCING_CONCEPT.md` §17.

## What Changes

- **Add** `pool-spec-publisher`: a publisher pipeline (hermes-inventory →
  role-lifecycle → demand-forecast → compose → publish → usage-feedback) reusing
  `PipelineRunner` unchanged; compose `fmo-pools/v1`; publish via `PUT /api/fmo/pools`
  with `Idempotency-Key = stable_hash(canonical_payload)`; record in
  `published_generations`.
- **Modify** demand-forecast: the quality band becomes a declared **intent**
  (`category`, `min`, `max`, `relax`) against OmniRoute's `model_intelligence.score`;
  no capacity-derived widening.
- **Modify** the OmniRoute client version handshake to gate **contract acceptance**
  (`fmo-pools/v1`) instead of combo writes.

## Impact

- **Added capability**: `pool-spec-publisher`.
- **Modified**: `demand-forecast`, `omniroute-client`.
- **Reused as-is**: `pipeline.PipelineRunner`, `forecast.aggregate_demand` /
  `protected_demand` / `apply_historical_reserve` / `cold_start_demand`,
  `role_lifecycle.reconcile_roles`, `omniroute.OmniRouteClient`,
  `idempotency.hash_parts`, `audit.audit_change`.
- **No removals here** — old allocate+apply path stays live (separate slices remove it).
- **New table**: `published_generations`.
