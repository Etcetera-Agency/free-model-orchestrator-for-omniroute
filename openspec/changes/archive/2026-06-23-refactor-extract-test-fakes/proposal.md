# Change: Extract shared test fakes and split test_composition.py to mirror the stage packages

## Why

`tests/test_composition.py` is 3142 lines: 85 tests plus nine fake clients
(`QuotaSearchClient`, `PipelineOpsClient`, `PartiallyFailingQuotaSearchClient`,
`MultiComboOpsClient`, `AccountDiscoveryOpsClient`, `RecordingLlmRuntime`,
`FakeOpenAIClient`, `FakeInstructorCompletions`, `FakeInstructorClient`) that are
shared test infrastructure trapped inside the test file. The fakes belong next to
the existing `tests/_fixtures.py` / `tests/_stage_effects.py` support modules, and
the tests should mirror the new `composition_stages/` cluster modules so each test
file maps to one stage domain.

This slice also fixes a real fragility surfaced during analysis: the suite only
runs via `python -m pytest`; the bare `pytest` console script fails with
`ModuleNotFoundError: No module named 'tests'` because the repo root is not on
`sys.path`. Both entry points should work so `make test` and ad-hoc `pytest` are
interchangeable.

## What Changes

- Add `tests/_clients.py` housing the nine shared fake clients/runtimes; import
  them from there in every test that uses them.
- Split `tests/test_composition.py` into per-domain files mirroring the stage
  packages: `test_composition_discovery.py`, `_quota.py`, `_access.py`,
  `_runtime.py` (probing/telemetry/inventory/roles), `_apply.py`
  (allocation/diff/apply/rollback/audit). Every `@pytest.mark.spec` marker moves
  **with its test** so the executable-spec coverage gate stays green (the gate is
  the oracle that no scenario binding is dropped).
- Fix the import path so both entry points resolve the `tests` package: add
  `tests/__init__.py` (and/or set `pythonpath = ["src", "."]`), and update the
  README/Makefile `test` target to match.

## Impact

- Affected specs: `system-architecture` (ADDED structural requirement)
- Affected code: `tests/test_composition.py` → `tests/_clients.py` +
  `tests/test_composition_*.py`; `tests/__init__.py` / `pyproject.toml`
  `[tool.pytest.ini_options].pythonpath`; `Makefile`, `README.md`. No production
  code changes. Oracle: the same set of tests pass, `test_spec_coverage.py` stays
  green (no marker lost), and both `pytest` and `python -m pytest` collect.
- Best done after the stage splits so the test files can mirror the final module
  boundaries, but the fake-extraction and import-path fix are independent and may
  land first.
