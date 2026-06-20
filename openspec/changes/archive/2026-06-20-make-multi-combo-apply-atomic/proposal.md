# Change: Make multi-combo apply all-or-nothing

## Why

`_apply_stage` (`src/fmo/composition.py:1191-1219`) applies each role's combo in a
loop and only writes the `phase='applied'` snapshots **after** the loop
completes. If combo N fails its smoke test, the stage rolls back combo N to its
`before` state and returns immediately. Combos 1..N-1 that already succeeded:

- remain mutated in OmniRoute,
- are never written as `applied` snapshots, so the `audit` stage cannot see them
  (it reads `phase='applied'`),
- are never rolled back.

The result is a partial apply that leaves OmniRoute changed while the database
has no record of it — silent, undetected drift, contradicting the "minimal-diff
apply with snapshot + audit + rollback" architecture pattern in `project.md`.

## What Changes

- A run that touches multiple `fmo-` combos SHALL be all-or-nothing: if any combo
  fails its smoke test, every combo already applied in that run SHALL be rolled
  back to its pre-change state before the stage returns.
- Each successful combo's `applied` snapshot SHALL be persisted such that, on a
  later failure in the same run, every applied combo is recoverable for rollback
  and visible to `audit` — no combo may be mutated in OmniRoute without a
  corresponding persisted record.
- On a rollback triggered by partial failure, the stage SHALL report
  `apply_failed_rolled_back` (exit 6), or `rollback_failed` (exit 7) if any
  restore call fails.

## Impact

- Affected specs: `combo-applier` (ADDED: atomic multi-combo apply).
- Affected code: `src/fmo/composition.py` (`_apply_stage` loop, snapshot
  persistence ordering, rollback of already-applied combos).
- No schema change (uses existing `combo_snapshots`).
