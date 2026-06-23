# Change: Drain the allocation/apply/rollback/audit bodies and delete `_legacy.py`

## Why

Terminal slice of the three-part drain (front → middle → **back**). The two prior
slices empty the front- and middle-of-pipeline clusters out of
`composition_stages/_legacy.py`. This slice drains the remaining back-of-pipeline
bodies, gives the shared spine (the `Stage*` dataclasses and the base
`_production_stage_adapters` builder) a real home, and **deletes `_legacy.py`** so
no delegation/monolith module remains under `fmo.composition_stages`. After this
slice navigating to any stage lands in its domain module, completing the "stage
domains live in separate modules" intent end to end.

## What Changes

- **Move into `apply.py`** (deleting the `_legacy` wrappers): `_diff_stage`,
  `_apply_stage`, `_review_diff`, `_review_payload`, the apply-safety checks
  (`_derive_apply_stage_safety`, `_desired_apply_endpoint_ids`,
  `_desired_endpoints_have_current_quota_safety`, `_endpoint_quota_row_is_safe`,
  `_desired_endpoints_have_current_probe_success`), the snapshot/rollback mutation
  helpers (`_persist_applied_snapshot`, `_rollback_apply_mutations`,
  `_delete_applied_snapshots_for_run`), `_read_current_combos`, `_smoke_combo`,
  and `APPLY_STAGE_EVIDENCE_MAX_AGE`.
- **Move into `allocation.py`**: `_demand_forecast_stage`, `_allocation_stage`,
  `_configured_router_input`, `_capacity_weight`.
- **Move into `rollback.py`**: `_rollback_stage`, `_rollback_targets`,
  `_rollback_combo_id`.
- **Move into `audit.py`**: `_audit_stage`.
- **Move the cross-cluster helper bodies into `_helpers.py`**: `_effect_result`,
  `_adapter_stage`, `_not_implemented_stage`, `_omniroute_instance_id` (the
  slug/hash/quota-math re-exports already live here from
  `refactor-unify-shared-helpers`; keep them as re-exports so the
  `getmodule(...) != _helpers` oracle still holds).
- **Relocate the shared spine into a new `_base.py`**: the `StageDependencies`,
  `StageAdapters`, and `FreeModelChanges` dataclasses, the `StageAdapter` type
  alias, and the base `_production_stage_adapters()` builder. Collapse the
  two-layer adapter map (base in `_legacy` + `__init__` override) into a single
  `_production_stage_adapters()` that references the now-local stage functions,
  and remove the `_legacy._production_stage_adapters = …` monkeypatch.
- **Delete `src/fmo/composition_stages/_legacy.py`** and drop every
  `from . import _legacy` / `from ._legacy import …` line. The `__init__` shim
  keeps the public re-export surface byte-identical.
- Grep for residual `_legacy.*` reads and repoint them at their canonical
  `fmo.idempotency` / `fmo.quota_normalize` / `_helpers` source.
- Fix the remaining pyright errors that surface once the monolith is gone.

## Impact

- **Affected specs:** `system-architecture` — ADD "Stage bodies are defined in
  their domain modules" (closes the delegation loophole package-wide and forbids
  any `_legacy` module); MODIFY "Allocation, apply, rollback, and audit stages are
  dedicated modules" from "a module exists" to "the module *defines* the stage"
  and from "no monolithic `composition_stages` module" to "no `_legacy`
  delegation module".
- **Affected code:** `src/fmo/composition_stages/_legacy.py` deleted;
  back-of-pipeline bodies land in `apply.py` / `allocation.py` / `rollback.py` /
  `audit.py`; spine lands in new `_base.py`; `__init__` adapter map simplified.
- **External surface unchanged:** `fmo.composition` imports from the package root;
  `tests/_composition_support` imports `_smoke_combo` from the package root; both
  keep working through the `__init__` shim.
- **Behavior-preservation oracle:** the **full** existing pytest suite —
  `tests/test_runtime_documentation.py` (module-structure + `_legacy` non-existence
  + `getmodule(...) != _helpers`), `tests/test_composition_*.py`,
  `tests/test_allocation.py`, `tests/test_advisory.py` — passes unchanged. No
  stage behavior, apply-safety decision, persisted shape, idempotency key, or exit
  code changes.
- **Depends on** `refactor-drain-stages-discovery` and
  `refactor-drain-stages-runtime` (both must be drained before `_legacy.py` can be
  deleted), plus the archived `refactor-split-stages-apply` and
  `refactor-unify-shared-helpers`.
