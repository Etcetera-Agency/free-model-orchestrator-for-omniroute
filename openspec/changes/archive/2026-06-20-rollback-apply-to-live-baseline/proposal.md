# Change: Roll back apply to the live pre-change baseline

## Why

On smoke failure, `_apply_stage` restores the combo by posting the `before`
value taken from the `diff` snapshot's `state_json`
(`src/fmo/composition.py:1193,1204`). That `before` was recorded at **diff** time.
This is a daily batch: meaningful time passes between `diff` and `apply`, and the
existing `Transactional apply with smoke test` requirement already mandates
re-reading current state and verifying its hash before mutating. If the live
combo diverged from the diff-time `before` (a manual edit, a previous run, drift),
restoring the stale `before` writes a *wrong* configuration on rollback instead
of returning the combo to the state it actually had immediately before this apply.

## What Changes

- The applier SHALL capture the rollback baseline from the live combo state read
  immediately before mutating it (the same read used for the hash/precondition
  check), not from the diff-time `before` field.
- On smoke failure the applier SHALL restore that captured live baseline.
- If the live state at apply time differs from the diff-time `before`, the apply
  SHALL follow the existing drift-protection path (conflict / require force)
  rather than silently overwriting.

## Impact

- Affected specs: `combo-applier` (MODIFIED: `Rollback on failure`).
- Affected code: `src/fmo/composition.py` (`_apply_stage`, `_read_current_combos`
  capture and reuse for rollback).
- No schema change.
