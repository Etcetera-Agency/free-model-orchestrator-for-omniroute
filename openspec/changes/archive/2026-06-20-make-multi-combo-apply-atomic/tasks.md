## 1. Persist each applied combo before moving on

- [x] 1.1 Failing test: after combo 1 is applied and combo 2 fails smoke, combo 1
      has a persisted record recoverable for rollback (no OmniRoute mutation
      without a DB record)
- [x] 1.2 Implement per-combo persistence of the applied state inside the apply
      loop (within the run's transaction boundary)

## 2. Roll back the whole run on partial failure

- [x] 2.1 Failing test: two-combo run where combo 2 fails smoke restores BOTH
      combo 1 and combo 2 to their pre-change state in OmniRoute
- [x] 2.2 Failing test: the run reports `apply_failed_rolled_back` (exit 6) on a
      successful rollback of the partial apply
- [x] 2.3 Failing test: a restore call that itself raises yields
      `rollback_failed` (exit 7)
- [x] 2.4 Implement all-or-nothing rollback of every already-applied combo

## 3. Audit sees only fully-applied runs

- [x] 3.1 Failing test: after a rolled-back partial apply, the `audit` stage sees
      no `applied` combo from that run
- [x] 3.2 Implement snapshot cleanup/commit semantics consistent with rollback

## 4. Validation

- [x] 4.1 Targeted pytest for apply/audit stages
- [x] 4.2 Full `pytest -q`
- [x] 4.3 Bind tests with `@pytest.mark.spec(...)` and shrink the pending list
- [x] 4.4 `openspec validate make-multi-combo-apply-atomic --strict`
