# Implementation Tasks

- [ ] Verify cutover gate: OmniRoute accepts `fmo-pools/v1`, runs shadow solve, applies atomically, and is confirmed as the single combo writer before any destructive allocation/apply removal.
- [ ] Remove the `allocation`, `diff`, and `apply` stages from the pipeline stage list.
- [ ] Delete `src/fmo/allocation.py` and `src/fmo/composition_stages/allocation.py`.
- [ ] Delete `src/fmo/applier.py`, `src/fmo/apply_guard.py`, and `composition_stages/{apply,rollback}.py`.
- [ ] Remove `audit.rollback_run` and combo-rollback paths.
- [ ] Drop `allocation_plans`, `global_allocation_plans`, `combo_snapshots` tables.
- [ ] Remove now-dead tests for allocation/apply; keep the suite green.
- [ ] Verify no remaining caller writes combos (single-writer invariant holds).
