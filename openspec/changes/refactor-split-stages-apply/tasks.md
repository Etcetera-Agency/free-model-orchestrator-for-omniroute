## 1. Oracles

- [ ] 1.1 Write failing test: allocation, apply, rollback, and audit stages live
      in dedicated modules and `composition_stages.py` no longer exists as a
      monolithic module (the package root holds only the shim + dataclasses),
      bound to `system-architecture::Allocation, apply, rollback, and audit
      stages live in dedicated modules`.
- [ ] 1.2 Write failing test: the cross-cluster shared helpers
      (`_effect_result`, `_canonical_slug`, `_hash_parts`, quota-math helpers,
      adapter helpers) are defined once in a single `_helpers` module and
      imported by the domain modules, bound to
      `system-architecture::Shared stage helpers live in one helpers module`.

## 2. Extract the back-of-pipeline clusters

- [ ] 2.1 Move demand-forecast + allocation into `allocation.py`.
- [ ] 2.2 Move the diff/apply stages, apply-safety checks, and snapshot/rollback
      mutation helpers into `apply.py`.
- [ ] 2.3 Move the rollback stage + targets into `rollback.py`.
- [ ] 2.4 Move the audit stage into `audit.py`.

## 3. Drain shared helpers and delete the monolith

- [ ] 3.1 Move the cross-cluster helpers into `_helpers.py`; repoint every domain
      module's imports.
- [ ] 3.2 Delete `composition_stages.py`; confirm the `__init__` shim still
      re-exports the identical public surface.
- [ ] 3.3 Fix the remaining pyright errors in the moved modules.

## 4. Close out

- [ ] 4.1 `make check` clean.
- [ ] 4.2 Run the allocation/advisory/composition test files then the full
      suite; it passes unchanged.
- [ ] 4.3 Remove the two bound scenarios from `tests/spec_coverage_pending.txt`
      and `EXPECTED_ACTIVE_PENDING`.
- [ ] 4.4 `openspec validate refactor-split-stages-apply --strict`.
