## 1. Idempotent revert writes

- [x] 1.1 Write failing test: the in-apply rollback after a smoke failure issues
      each revert `PUT /api/combos/{id}` with an `Idempotency-Key` derived from
      the restored state, bound to `combo-applier::Revert write carries an
      idempotency key`.
- [x] 1.2 Extend the test to the top-level `rollback` command path so its restore
      writes carry the same key, and assert a retried revert with the same key is
      not double-applied.
- [x] 1.3 Pass `idempotency_key` on the revert `PUT`s in
      `_rollback_apply_mutations` and `_rollback_stage`, derived from the restored
      `before` state (same hashing as apply writes).

## 2. Close out

- [x] 2.1 Run targeted pytest (full suite deferred to end of batch per operator instruction).
- [x] 2.2 Remove the now-bound scenario from `tests/spec_coverage_pending.txt`
      and `EXPECTED_ACTIVE_PENDING` in `tests/test_runtime_documentation.py`.
- [x] 2.3 `openspec validate add-rollback-idempotency --strict`.
