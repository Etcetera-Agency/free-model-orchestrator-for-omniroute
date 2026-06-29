# Implementation Tasks

- [x] Verify cutover gate: OmniRoute accepts `fmo-pools/v1`, runs shadow solve, applies atomically, and is confirmed as the single combo writer before any destructive allocation/apply removal. User waived live gate on 2026-06-29 for pure FMO spec removal; follow-up remains in `openspec/TODO.md`.
- [x] Remove the `allocation`, `diff`, and `apply` stages from the pipeline stage list.
- [x] Delete `src/fmo/allocation.py` and `src/fmo/composition_stages/allocation.py`.
- [x] Delete `src/fmo/applier.py`, `src/fmo/apply_guard.py`, and `composition_stages/{apply,rollback}.py`.
- [x] Remove `audit.rollback_run` and combo-rollback paths.
- [x] Drop `allocation_plans`, `global_allocation_plans`, `combo_snapshots` tables.
- [x] Remove now-dead tests for allocation/apply; keep the suite green.
- [x] Verify no remaining caller writes combos (single-writer invariant holds).
