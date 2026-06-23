# Change: Split the allocation/apply/rollback/audit stages and centralize stage helpers

## Why

Final slice decomposing `composition_stages.py` (after
`refactor-split-stages-discovery` and `-runtime`). It extracts the **back of the
pipeline** — demand forecast, allocation, diff, apply, rollback, audit — which
carries the apply-safety logic, and then drains the remaining cross-cluster
helpers into a single `_helpers.py`. After this slice `composition_stages.py` is
gone: the package root is just the `__init__` shim plus the dataclasses, and
every stage lives in its domain module. This completes the
`system-architecture::Stage domains live in separate modules` intent end to end.

## What Changes

- Extract into focused modules under `fmo.composition_stages`:
  - `allocation.py` — `_demand_forecast_stage`, `_allocation_stage`,
    `_configured_router_input`.
  - `apply.py` — `_diff_stage`, `_review_diff`, `_review_payload`,
    `_apply_stage`, `_persist_applied_snapshot`, `_rollback_apply_mutations`,
    `_combo_models_idempotency_key`, `_delete_applied_snapshots_for_run`,
    `_derive_apply_stage_safety`, `_desired_apply_endpoint_ids`,
    `_desired_endpoints_have_current_quota_safety`, `_endpoint_quota_row_is_safe`,
    `_desired_endpoints_have_current_probe_success`, `_read_current_combos`,
    `_smoke_combo`.
  - `rollback.py` — `_rollback_stage`, `_rollback_targets`, `_rollback_combo_id`.
  - `audit.py` — `_audit_stage`.
- Move the cross-cluster shared helpers used by every domain into `_helpers.py`:
  `_effect_result`, `_canonical_slug`, `_hash_parts`, `_quota_metric`,
  `_quota_limit`, `_remaining_amount`, `_not_implemented_stage`,
  `_adapter_stage`, `_omniroute_instance_id`, and the `Stage*` dataclasses /
  `_production_stage_adapters` (or keep the dataclasses in `__init__`).
- Delete the now-empty `composition_stages.py`; the `__init__` shim keeps the
  public surface identical.
- Fix the remaining pyright errors in the moved modules.

> Note: the quota-math helpers (`_quota_metric`, `_quota_limit`,
> `_remaining_amount`) are parked in `_helpers.py` here and relocated next to
> `quota_normalize`/`quota_manager` in `refactor-unify-shared-helpers`; this
> slice only moves them out of the monolith.

## Impact

- Affected specs: `system-architecture` (ADDED structural requirement)
- Affected code: `src/fmo/composition_stages.py` removed; new
  `src/fmo/composition_stages/{allocation,apply,rollback,audit,_helpers}.py`.
  Oracle: `tests/test_allocation.py`, `tests/test_advisory.py`,
  `tests/test_composition.py` (apply/rollback/audit scenarios) pass unchanged.
- Depends on `refactor-split-stages-discovery` and `refactor-split-stages-runtime`.
