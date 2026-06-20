# Completion Review: add-runtime-bootstrap-and-locks

## Summary

- Added `src/fmo/bootstrap.py` to build `StartupConfig` from environment variables, validate static config and OmniRoute health before dispatch, and map validation failures to exit code 3.
- Replaced `cli.main()` hardcoded empty argv path with real argv/env bootstrap and validation-derived preconditions.
- Added DB-backed run locks through the repository layer and `src/fmo/scheduler.py` for cron/manual/event/urgent triggers.

## Verification

- `uv run --extra test pytest -q tests/test_bootstrap.py tests/test_scheduler.py`
- `uv run --extra test pytest -q tests/test_bootstrap.py tests/test_scheduler.py tests/test_spec_coverage.py`
- `openspec validate add-runtime-bootstrap-and-locks --strict`
- `uv run --extra test pytest -q`
- `openspec validate --all --strict`
- `uv run --extra test pytest -q` after archive
