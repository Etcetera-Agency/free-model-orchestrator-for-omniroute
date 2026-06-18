# Completion Review: update-cli-stage-execution

## Summary

- Extended `run_cli()` with injectable pipeline runner dispatch for per-stage commands, `full`, `apply`, and `rollback`.
- Surfaced runner exit codes for stage failures and apply/rollback gating outcomes.
- Added injectable diagnostics reading for `explain-endpoint` and `explain-role`, plus local dry-run behavior that never calls `/api/combos/test`.

## Verification

- `uv run --extra test pytest -q tests/test_cli.py tests/test_web_cookie_cli.py`
- `uv run --extra test pytest -q tests/test_cli.py tests/test_web_cookie_cli.py tests/test_spec_coverage.py`
- `openspec validate update-cli-stage-execution --strict`
- `uv run --extra test pytest -q`
- `openspec validate --all --strict`
- `uv run --extra test pytest -q` after archive
