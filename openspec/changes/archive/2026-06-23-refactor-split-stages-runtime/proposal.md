# Change: Split the probing/telemetry/inventory/role stages out of composition_stages.py

## Why

Second of three slices decomposing `composition_stages.py` into the
`composition_stages/` package (see `refactor-split-stages-discovery`). This slice
extracts the **middle of the pipeline**: probing, telemetry sync, Hermes
inventory, role lifecycle, and role scoring — the stages that observe live
endpoint health and turn it into scored, lifecycle-managed roles. Role scoring
carries the largest helper cluster in the file (health/stability/latency
components, quality-band seeding, AA-metric and health lookups), so isolating it
removes most of the remaining bulk.

## What Changes

- Extract into focused modules under `fmo.composition_stages`:
  - `probing.py` — `_probing_stage`.
  - `telemetry.py` — `_telemetry_sync_stage`.
  - `inventory.py` — `_hermes_inventory_stage`, `_read_hermes_inventory`,
    `_run_hermes_inspector`.
  - `roles.py` — `_role_lifecycle_stage`, `_role_scoring_stage`,
    `_seed_quality_bands`, `_quality_band_candidates`,
    `_latest_protected_requests`, `_latest_aa_metrics_by_model`,
    `_latest_health_by_endpoint`, `_latest_remaining_by_pool`,
    `_health_component`, `_stability_component`, `_latency_component`,
    `_context_window_eligibility`, `_quality_gate_eligibility`,
    `_roles_needing_quality_recalibration`, `_insert_health_observation`.
- Cross-cluster shared helpers still live in `composition_stages.py`; they move
  in `refactor-split-stages-apply`. The moved modules import them unchanged.
- Fix the pyright errors in the moved modules (notably `telemetry.py`'s
  `Unknown | None` reads) as they are extracted.

## Impact

- Affected specs: `system-architecture` (ADDED structural requirement)
- Affected code: `src/fmo/composition_stages.py` (stages removed), new
  `src/fmo/composition_stages/{probing,telemetry,inventory,roles}.py`. Oracle:
  `tests/test_scoring.py`, `tests/test_role_lifecycle.py`,
  `tests/test_telemetry_ingestion.py`, `tests/test_hermes_inventory_real_shapes.py`,
  `tests/test_composition.py` pass unchanged.
- Depends on `refactor-split-stages-discovery` (package + shim already in place).
