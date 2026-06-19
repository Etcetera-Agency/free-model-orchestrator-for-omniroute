# Change: Make run-lock acquisition atomic

## Why

The current scheduler lock repository performs a read for an existing held lock,
then inserts a new held row. Two separate worker processes can run that sequence
at the same time, both observe no held row, and both acquire the same logical
lock.

That breaks the scheduler invariant that daily, provider-scan, and combo-apply
runs are mutually excluded across process boundaries.

## What Changes

- Add a database-enforced active-lock uniqueness rule for held run-lock rows.
- Replace check-then-insert lock acquisition with one atomic insert that returns
  a token only for the winner.
- Keep lock release row-backed by updating the held row to released with
  `finished_at`.
- Add a concurrent acquisition test using real PostgreSQL connections.
- Add migration coverage so upgraded databases receive the same lock safety as
  fresh installs.

## Impact

- Affected specs: `scheduler`
- Affected code: `reference/db/schema.sql`, `reference/db/migrations/*`,
  `src/fmo/persistence.py`, `src/fmo/scheduler.py`, `tests/test_scheduler.py`
- Data impact: existing released lock rows remain unchanged; only active
  `sync_runs` rows with `run_type = 'lock'`, `status = 'held'`, and
  `finished_at IS NULL` are constrained to one row per logical lock name.
