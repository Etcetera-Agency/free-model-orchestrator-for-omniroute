# Change: Derive apply-stage quota and probe safety from persisted state

## Why

`derive-apply-preconditions` (archived) fixed the **entrypoint** so
`bootstrap_and_dispatch` no longer passes a hardcoded `True`. But the composed
production `apply` stage re-checks preconditions a second time and there it still
hardcodes the two safety inputs:

```python
# src/fmo/composition.py:1174-1183 (_apply_stage)
check_apply_preconditions(ApplyPreconditions(
    db_available=True,
    snapshot_saved=bool(diffs),
    desired_state_valid=...,
    quota_safe=True,      # never evaluated
    probes_passed=True,   # never evaluated
))
```

So the stage that actually mutates OmniRoute proceeds even when quota gates or
probe evidence are failing/stale/missing. This violates the core invariant ("no
probe or production request may exceed confirmed free capacity") and the README
guarantee that apply is "guarded by … quota safety, and passing smoke/probe
checks". The entrypoint guard is necessary but not sufficient: state can change
between entrypoint evaluation and the stage running inside the daily batch.

## What Changes

- `_apply_stage` SHALL derive `quota_safe` and `probes_passed` from persisted
  repository state for the combos it is about to apply, not from constants.
- `quota_safe` is `True` only when every endpoint in the desired combos has a
  current quota-safety record above the safety buffer with confirmed hard-stop
  behavior; otherwise `False`.
- `probes_passed` is `True` only when every endpoint in the desired combos has a
  passing, non-stale probe/smoke result; otherwise `False`.
- Fail closed: missing, unknown, or stale evidence yields `False`, and the stage
  returns `unsafe_to_apply` (exit 5) without mutating any combo.

## Impact

- Affected specs: `combo-applier` (ADDED: apply stage derives safety inputs).
- Affected code: `src/fmo/composition.py` (`_apply_stage`), reading
  quota/probe repositories; possibly small repository read helpers.
- No schema change.
