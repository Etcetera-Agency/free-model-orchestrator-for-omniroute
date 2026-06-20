# Completion Review: add-persistence-repositories

## Summary

- Added `src/fmo/persistence.py` with a PostgreSQL `Database.transaction()` wrapper and repository groups for runs, providers, accounts, canonical models, endpoints, quota source snapshots, quota rules, probes, roles, scores, allocation plans, combo snapshots, and audit log entries.
- Added real PostgreSQL coverage in `tests/test_persistence.py` for rollback, commit durability, domain round-trips, idempotent writes, and content-hashed snapshot dedupe.
- Code Simplifier pass replaced broad SQL parameter collection with explicit provider upsert params.
- Follow-up discovered: existing direct SQL writers in `src/fmo/scanner.py` and
  `src/fmo/registry.py` still need repository migration during pipeline/CLI
  wiring. Tracked in repo-level `openspec/TODO.md`.

## Verification

- `uv run --extra test pytest -q tests/test_persistence.py`
- `uv run --extra test pytest -q`
- `openspec validate add-persistence-repositories --strict`
- `uv run --extra test pytest -q tests/test_persistence.py` after Code Simplifier pass
- `openspec validate --all --strict`
- `uv run --extra test pytest -q tests/test_persistence.py tests/test_spec_coverage.py`
- `uv run --extra test pytest -q -m 'not live'`

## Notes

- Post-archive `uv run --extra test pytest -q` reached 213 passed, then failed
  on `tests/test_live_external_sources.py::test_artificial_analysis_live_free_snapshot_paginates`
  because the live Artificial Analysis API returned HTTP 429.
