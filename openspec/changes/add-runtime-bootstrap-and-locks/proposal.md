# Change: Add runtime bootstrap, scheduler and run-lock persistence

## Why

`scheduler` specifies a daily cron run with run locks and trigger types, and
`config.py` has `StartupConfig` + `validate_startup`, but nothing loads the
config from the environment, validates it at startup, schedules the daily run,
or persists the locks. `main()` calls `run_cli([], preconditions_ok=True)` with
an empty argv and a hardcoded precondition, so there is no real service
entrypoint. This slice makes the service actually bootstrap and run on schedule.

## What Changes

- Add `src/fmo/bootstrap.py`: build `StartupConfig` from environment variables,
  run `validate_startup` (static config + OmniRoute health) before any pipeline
  run, and surface validation failure as exit code 3.
- Replace the trivial `main()` so the real entrypoint loads config, then
  dispatches to the CLI/runner.
- Add persistent run locks (global daily-run lock, per-provider scan lock,
  global combo-apply lock) stored in PostgreSQL via the repository layer; a new
  daily run does not start while a previous one is unfinished.
- Add a scheduler that fires the full pipeline at `HERMES_INVENTORY_CRON` and
  supports manual full/provider/role and event-driven/urgent triggers.

## Impact

- Affected specs: `runtime-bootstrap` (new capability); `scheduler` (ADDED
  run-lock persistence + service-entrypoint requirements).
- Affected code: new `src/fmo/bootstrap.py`; `src/fmo/cli.py` `main()`;
  consumes `add-pipeline-orchestration` runner and `persistence`.
- Depends on `add-persistence-repositories` and `add-pipeline-orchestration`.
