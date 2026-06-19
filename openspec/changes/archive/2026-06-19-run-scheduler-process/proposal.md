# Change: Run the scheduler as a real process

## Why

`scheduler.py` provides the run-lock manager and cron-firing helpers, and unit
tests cover `scheduler::Scheduler fires at cron time` and
`scheduler::Manual trigger starts a run`. But nothing in production **hosts** a
process that owns the cron loop: no entrypoint imports the scheduler, so the
"daily batch pipeline" the README and `scheduler` spec promise never actually
fires. Consequently the behavioral scenarios `scheduler::Scheduled daily run`,
`scheduler::Overlapping daily runs`, and `scheduler::Urgent run after paid
charge` remain on the pending allowlist with no end-to-end coverage.

## What Changes

- Add a long-running scheduler entrypoint (CLI subcommand `serve` / console
  script) that owns the cron loop driven by `HERMES_INVENTORY_CRON`, acquires the
  persistent daily run-lock, and dispatches full runs through the production
  runner from `compose-production-pipeline`.
- Route manual, event-driven, and urgent triggers through the same run-lock so an
  out-of-schedule run starts only when no run holds the lock.
- The scheduler SHALL never call `/api/combos/test`.
- Bind the three pending `scheduler::*` behavioral scenarios to end-to-end tests
  and remove them from `tests/spec_coverage_pending.txt` (the allowlist shrinks).

## Impact

- Affected specs: `scheduler` (ADDED: scheduler service entrypoint).
- Affected code: new scheduler entrypoint wiring in `src/fmo/cli.py` /
  `src/fmo/scheduler.py`; consumes the composed runner and run-lock manager.
- Depends on `compose-production-pipeline`, `add-runtime-bootstrap-and-locks`.
