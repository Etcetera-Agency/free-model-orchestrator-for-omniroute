# Change: Wire probing, telemetry-sync, and quota-sync stages

## Why

After the matching/access slice, `probing`, `telemetry-sync`, and `quota-sync`
remain unwired and stop the `full` run. Their modules (`src/fmo/probes.py`,
`src/fmo/telemetry.py`, `src/fmo/quota_manager.py`,
`src/fmo/quota_attribution.py`) are implemented and unit tested but not imported
by production composition.

Probing is the stage most bound by the core invariant: it may only run against
confirmed-free endpoints within reserved capacity. Telemetry and quota sync then
feed scoring with normalized health and remaining-quota state.

## What Changes

- Add production adapters driving `probes`, `telemetry`, and `quota_manager`
  (with `quota_attribution`) from the composed runtime.
- Enforce the core invariant in the production path: the probe adapter SHALL run
  only for `confirmed`-free endpoints with reserved capacity, and SHALL never
  exceed confirmed free capacity.
- Persist probe results, normalized telemetry, and synced remaining-quota state
  through the repository.
- Add executable effect tests asserting probe gating, persisted rows, and that
  swapping any adapter for unconditional success fails.

## Impact

- Affected specs: `pipeline-orchestration`.
- Affected code: `src/fmo/composition.py`, `src/fmo/probes.py`,
  `src/fmo/telemetry.py`, `src/fmo/quota_manager.py`,
  `src/fmo/quota_attribution.py`, `src/fmo/persistence.py`, `tests/`.
- Depends on: `wire-matching-access-stages`.
- No new external service contract; probing uses the existing OmniRoute
  OpenAI-compatible boundary.
