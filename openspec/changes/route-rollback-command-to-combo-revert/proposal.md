# Change: Route the top-level `rollback` command to combo revert

## Why

The README, `cli-and-operations`, and `audit-rollback` all treat `rollback` as a
combo operation: the README lists exit code 7 `rollback_failed`, `cli` requires
"`apply` and `rollback` SHALL run through the runner's fail-closed gating", and
`audit-rollback` requires rolling back "one combo, all combos of one run". But in
the runtime the top-level `rollback` command dispatches to
`_rollback_latest_aa_migration` (`src/fmo/composition.py:1277-1278` via the
`rollback` mapping), which reverts an AA-index threshold — a different capability
that already has its own `aa-index rollback` subcommand. There is no operator
path that reverts a previously applied combo run, so the documented combo
rollback and exit codes 6/7 are unreachable from the CLI.

## What Changes

- The top-level `rollback` command SHALL revert applied `fmo-` combos from
  persisted snapshots — one combo (`--endpoint`/`--role`) or all combos of a run
  (`--run-id`) — through the runner's fail-closed gating, distinct from
  `aa-index rollback`.
- It SHALL restore each targeted combo to its persisted pre-change state, record
  the rollback in audit, and return `0` on success or `7` (`rollback_failed`)
  when a restore call fails.
- `aa-index rollback` SHALL remain the only path that reverts AA-index threshold
  migrations; the two SHALL NOT be conflated.

## Impact

- Affected specs: `audit-rollback` (MODIFIED: `Rollback scopes`).
- Affected code: `src/fmo/composition.py` (`rollback` command routing, a combo
  revert path reusing the applier; stop routing `rollback` to
  `_rollback_latest_aa_migration`).
- No schema change (reuses `combo_snapshots` + audit).
