## 1. Environment bootstrap

- [x] 1.1 Failing test: missing/invalid env (URL scheme, DATABASE_URL, inventory mode, cron) raises and maps to exit code 3
- [x] 1.2 Implement `build_startup_config()` reading env into `StartupConfig`
- [x] 1.3 Failing test: `validate_startup` runs the OmniRoute health check before any pipeline run
- [x] 1.4 Wire bootstrap to call `validate_startup` before dispatch

## 2. Real entrypoint

- [x] 2.1 Failing test: `main()` parses real argv (not empty) and derives preconditions from validation, not a hardcoded flag
- [x] 2.2 Replace `main()` to bootstrap config then dispatch to the CLI/runner

## 3. Persistent run locks

- [x] 3.1 Failing test: a second daily run does not start while a global daily-run lock is held
- [x] 3.2 Failing tests: per-provider scan lock and global combo-apply lock block concurrent holders
- [x] 3.3 Implement DB-backed locks via the repository layer with release on completion/failure

## 4. Scheduler and triggers

- [x] 4.1 Failing test: scheduler fires the full pipeline at the configured cron time
- [x] 4.2 Failing tests: manual full/provider/role and event-driven/urgent triggers start a run; scheduler never calls `/api/combos/test`
- [x] 4.3 Implement the cron-driven scheduler over the pipeline runner

## 5. Validation

- [x] 5.1 Run targeted pytest for `tests/test_bootstrap.py` and `tests/test_scheduler.py`
- [x] 5.2 Run full `pytest -q`
- [x] 5.3 `openspec validate add-runtime-bootstrap-and-locks --strict`
