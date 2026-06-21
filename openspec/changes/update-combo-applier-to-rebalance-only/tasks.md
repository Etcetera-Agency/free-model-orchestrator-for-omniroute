# Implementation Tasks (TDD)

Write each test first (red) → green → refactor. Mock only the OmniRoute boundary
with recorded real combo shapes. PostgreSQL is real. OmniRoute combo routes:
`../OmniRoute` (`src/app/api/combos`).

## Tasks

- [ ] 1. TEST: when a desired `fmo-` diff's combo id is **absent** from the live
  OmniRoute set, apply issues **no** `POST /api/combos/{id}` for it and reports
  it as `unmanaged_combo` → implement the existence gate from
  `_read_current_combos` before mutation.
- [ ] 2. TEST: an absent combo is skipped without failing the run — other present
  combos in the same apply still mutate and smoke-test → implement skip-not-fail.
- [ ] 3. TEST: apply never issues a DELETE for any combo → assert no delete call
  on any path (success, drift, rollback).
- [ ] 4. TEST: an existing `fmo-` combo still rebalances with the full drift /
  smoke / rollback behavior unchanged → regression guard.
- [ ] 5. TEST: `ComboApplier.apply()` refuses an id not in its `current` map
  → add the defense-in-depth guard.
- [ ] 6. Remove the unknown-role immediate-inventory expectation **at
  implementation** (not in the docs pass, to avoid dangling the bound marker
  `hermes-inventory::Unknown role observed` at `tests/test_role_lifecycle.py:28`):
  in one commit, MODIFY the living `hermes-inventory` `Daily and unknown-role
  inventory` requirement to daily + manual/event only, delete the
  `Unknown role observed` scenario, and remove/repoint that test. Confirm
  `should_run_full_inventory` has no runtime caller and drop it.
- [ ] 7. Bind tests with `@pytest.mark.spec("...")`, drop matching lines from
  `tests/spec_coverage_pending.txt`, run full `pytest` and
  `openspec validate update-combo-applier-to-rebalance-only --strict`.
