## 1. Oracles

- [x] 1.1 Write failing test: `_demand_forecast_stage`, `_allocation_stage`,
      `_diff_stage`, `_apply_stage`, `_audit_stage`, and `_rollback_stage` resolve
      via `inspect.getmodule(...)` to
      `fmo.composition_stages.{allocation,apply,audit,rollback}` and **not** to
      `fmo.composition_stages._legacy`, bound to
      `system-architecture::Allocation, apply, rollback, and audit stages live in
      dedicated modules`.
- [x] 1.2 Write failing test: `fmo/composition_stages/_legacy.py` does not exist
      on disk and no package module imports `_legacy`, bound to
      `system-architecture::Stage bodies are defined in their domain modules`
      (mirror the `composition_stages.py` non-existence assertion at
      `tests/test_runtime_documentation.py:143`).

## 2. Drain the back-of-pipeline clusters

- [x] 2.1 Move `_diff_stage`, `_apply_stage`, the apply-safety checks, the review
      helpers (`_review_diff`, `_review_payload`), the snapshot/rollback mutation
      helpers, `_read_current_combos`, `_smoke_combo`, and
      `APPLY_STAGE_EVIDENCE_MAX_AGE` into `apply.py`; delete the wrappers.
- [x] 2.2 Move `_demand_forecast_stage`, `_allocation_stage`,
      `_configured_router_input`, `_capacity_weight` into `allocation.py`.
- [x] 2.3 Move `_rollback_stage`, `_rollback_targets`, `_rollback_combo_id` into
      `rollback.py`.
- [x] 2.4 Move `_audit_stage` into `audit.py`.

## 3. Relocate the shared spine

- [x] 3.1 Move the cross-cluster helper bodies (`_effect_result`,
      `_adapter_stage`, `_not_implemented_stage`, `_omniroute_instance_id`) into
      `_helpers.py`, keeping the slug/hash/quota-math re-exports unchanged.
- [x] 3.2 Move the `Stage*` / `FreeModelChanges` dataclasses and the
      `StageAdapter` type alias into a new `_base.py`.
- [x] 3.3 Move the base `_production_stage_adapters()` builder into `_base.py` and
      collapse the `__init__` override into a single map that references the
      now-local stage functions; remove the
      `_legacy._production_stage_adapters = …` monkeypatch.

## 4. Delete the monolith

- [x] 4.1 Delete `src/fmo/composition_stages/_legacy.py`; drop every
      `from . import _legacy` / `from ._legacy import …` line; confirm `__init__`
      still re-exports the identical public surface.
- [x] 4.2 Grep `src/` and `tests/` for residual `_legacy` references; repoint any
      helper read through a `_legacy.*` alias to its canonical
      `fmo.idempotency` / `fmo.quota_normalize` / `_helpers` source.

## 5. Close out

- [x] 5.1 `make check` clean (resolve the pyright `Any`-laundering errors that
      surface once the wrappers are gone).
- [x] 5.2 Run the focused stage test files green; defer the **full** pytest suite
      under both entry points to the final all-slice verification pass per the
      no-full-suite-after-each-slice instruction.
- [x] 5.3 Clear the bound scenarios from `tests/spec_coverage_pending.txt` and
      `EXPECTED_ACTIVE_PENDING` once green.
- [x] 5.4 `git diff --check`; `openspec validate refactor-drain-stages-apply --strict`.
