# Change: Carry an Idempotency-Key on rollback/revert combo writes

## Why

Apply combo writes pass an `Idempotency-Key` derived from the target state
(`src/fmo/composition_stages.py:1556`), but the revert paths do not:

- in-apply rollback after a smoke failure (`_rollback_apply_mutations`,
  `src/fmo/composition_stages.py:1611`)
- the top-level `rollback` command (`_rollback_stage`,
  `src/fmo/composition_stages.py:1714`)

Both `PUT /api/combos/{id}` without a key. A retried revert (transport retry or
re-run) can therefore be applied twice, defeating the idempotency contract that
apply already honors. Reverts are the most safety-sensitive writes, so they
should be at least as protected as forward applies.

## What Changes

- Every restore/revert combo write SHALL carry an `Idempotency-Key` derived from
  the restored combo state, matching the apply-write convention, so a retried
  revert is a no-op rather than a double-apply.

## Impact

- Affected specs: `combo-applier`
- Affected code: `src/fmo/composition_stages.py` (`_rollback_apply_mutations`,
  `_rollback_stage`), rollback tests.
