# Change: Drain the probing/telemetry/inventory/role stage bodies out of `_legacy.py`

## Why

Second of three drain slices (front → **middle** → back). The
`refactor-split-stages-runtime` slice created `probing.py`, `telemetry.py`,
`inventory.py`, and `roles.py` as one-line delegations to
`composition_stages/_legacy.py`; the middle-of-pipeline bodies — including the
whole role-scoring helper cluster — still live in the monolith. This slice moves
them into the modules that already front them. `_legacy.py` shrinks further but is
deleted only in the terminal `refactor-drain-stages-apply` slice.

## What Changes

- **Move into `probing.py`** (deleting the `_legacy` wrapper): `_probing_stage`,
  sourcing the `_remaining_requests` alias from `quota_normalize.remaining_amount`.
- **Move into `telemetry.py`**: `_telemetry_sync_stage`.
- **Move into `inventory.py`**: `_hermes_inventory_stage`, `_read_hermes_inventory`,
  `_run_hermes_inspector`.
- **Move into `roles.py`**: `_role_lifecycle_stage`, `_role_scoring_stage`, the
  role-scoring helper cluster (`_seed_quality_bands`, `_quality_band_candidates`,
  `_quality_gate_eligibility`, `_roles_needing_quality_recalibration`,
  `_context_window_eligibility`, `_stability_component`, `_health_component`,
  `_latency_component`, `_insert_health_observation`), the `_latest_*` read
  helpers (`_latest_aa_metrics_by_model`, `_latest_health_by_endpoint`,
  `_latest_protected_requests`, `_latest_remaining_by_pool`,
  `_latest_role_diagnostic`), and the `AA_SCORE_WEIGHTS` / `AA_SCORE_PERCENTILES`
  constants.
- Point each moved body at the canonical cross-cluster helpers directly instead
  of routing through `_legacy.*` aliases; drop the separate
  `from ._legacy import _latest_role_diagnostic` line in `__init__` once it is
  defined in `roles.py`.
- Update the `__init__` adapter map so the middle-of-pipeline adapters reference
  the now-local definitions; the base `_production_stage_adapters` in `_legacy`
  keeps building the rest until the terminal slice.
- Fix the pyright errors that surface once the middle-of-pipeline wrappers are
  gone.

## Impact

- **Affected specs:** `system-architecture` — MODIFY "Probing, telemetry,
  inventory, and role stages are dedicated modules" from "a module exists" to "the
  module *defines* the stage" (no delegation to `_legacy`).
- **Affected code:** middle-of-pipeline bodies leave `_legacy.py` for
  `probing.py` / `telemetry.py` / `inventory.py` / `roles.py`; `_legacy.py` stays
  (shrunk).
- **External surface unchanged:** the `__init__` shim re-exports each symbol from
  its domain module.
- **Behavior-preservation oracle:** focused role/telemetry/inventory/probing
  composition tests + `tests/test_runtime_documentation.py` pass unchanged; the
  full suite is deferred to the terminal slice.
- **Depends on** the archived `refactor-split-stages-runtime`. Independent of
  `refactor-drain-stages-discovery` (disjoint function sets); either order works.
