# Change: Remove FMO global allocation and combo apply

## Why

Cutover slice. Once the publisher works and `OMNIROUTE_FMO_POOLS_ENABLED` flips so
OmniRoute is the single writer of combo rows, FMO's global allocation and combo
apply are dead weight that would violate the single-writer invariant. Remove them.

Depends on `add-pool-spec-publisher` and the OmniRoute apply slice being live.

Concept: `FMO_SIDE_IMPLEMENTATION.md` §12, §13; `FMO_OMNIROUTE_POOL_BALANCING_CONCEPT.md` §17.

## What Changes

- **Remove** the `allocator` capability (global allocation, reservation, priority
  combo emission, degraded modes, allocator-side stability) — OmniRoute owns the solve.
- **Remove** the `combo-applier` capability (combo write, smoke, rollback, drift,
  preconditions, multi-combo atomicity) — OmniRoute owns the atomic apply.
- Delete `allocation.py`, `applier.py`, `apply_guard.py`, `audit.rollback_run`, and
  the `composition_stages/{allocation,apply,rollback}.py` stages; drop the `allocation`,
  `diff`, `apply` pipeline stages.

## Impact

- **Removed capabilities**: `allocator`, `combo-applier`.
- **Single-writer invariant**: after this slice OmniRoute is the only combo writer.
- **Depends on**: `add-pool-spec-publisher` + OmniRoute `add-fmo-pools-apply` live.
