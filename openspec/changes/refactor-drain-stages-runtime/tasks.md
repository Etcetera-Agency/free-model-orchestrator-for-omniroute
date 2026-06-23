## 1. Oracles

- [ ] 1.1 Write failing test: `_probing_stage`, `_telemetry_sync_stage`,
      `_hermes_inventory_stage`, `_role_lifecycle_stage`, and `_role_scoring_stage`
      resolve via `inspect.getmodule(...)` to
      `fmo.composition_stages.{probing,telemetry,inventory,roles}` and **not** to
      `fmo.composition_stages._legacy`, bound to
      `system-architecture::Probing, telemetry, inventory, and role stages live in
      dedicated modules`. (Extend the structural assertions in
      `tests/test_runtime_documentation.py`.)
- [ ] 1.2 Write failing test: the role-scoring helper cluster
      (`_health_component`, `_stability_component`, `_latency_component`,
      `_seed_quality_bands`, the `_latest_*` lookups) is defined in
      `fmo.composition_stages.roles`, bound to
      `system-architecture::Role scoring helpers move with the role stage`.

## 2. Drain probing and telemetry

- [ ] 2.1 Move `_probing_stage` into `probing.py`, sourcing `_remaining_requests`
      from `quota_normalize.remaining_amount`; delete the `_legacy` wrapper.
- [ ] 2.2 Move `_telemetry_sync_stage` into `telemetry.py`; delete the wrapper.

## 3. Drain inventory

- [ ] 3.1 Move `_hermes_inventory_stage`, `_read_hermes_inventory`,
      `_run_hermes_inspector` into `inventory.py`; delete the wrappers.

## 4. Drain roles

- [ ] 4.1 Move `_role_lifecycle_stage`, `_role_scoring_stage` and the
      role-scoring helper cluster (quality-band seeding/eligibility,
      health/stability/latency components, `_insert_health_observation`, the
      `_latest_*` lookups, `_latest_role_diagnostic`) and the
      `AA_SCORE_WEIGHTS`/`AA_SCORE_PERCENTILES` constants into `roles.py`; delete
      the wrappers and the `from ._legacy import _latest_role_diagnostic` line.

## 5. Rewire and close out

- [ ] 5.1 Repoint moved bodies at canonical helpers instead of `_legacy.*`
      aliases; update the `__init__` adapter map to reference the now-local
      definitions.
- [ ] 5.2 `make check` clean (resolve the pyright errors surfaced by the move).
- [ ] 5.3 Run the focused role/telemetry/inventory/probing composition + spec docs
      tests; defer the full suite to the terminal `refactor-drain-stages-apply`
      slice.
- [ ] 5.4 `git diff --check`; `openspec validate refactor-drain-stages-runtime --strict`.
