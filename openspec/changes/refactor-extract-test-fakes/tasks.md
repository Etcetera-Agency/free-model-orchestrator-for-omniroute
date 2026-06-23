## 1. Oracles

- [ ] 1.1 Write failing test: the shared fake clients/runtimes are importable
      from `tests._clients` and `tests/test_composition.py` no longer defines
      them inline, bound to
      `system-architecture::Test fakes live in a shared test-support module`.
- [ ] 1.2 Write failing test: per-domain composition test files exist mirroring
      the stage clusters and `tests/test_composition.py` is retired, bound to
      `system-architecture::Composition tests mirror the stage packages`.
- [ ] 1.3 Write failing test: the suite collects under both `pytest` and
      `python -m pytest` (the `tests` package resolves without relying on cwd on
      `sys.path`), bound to
      `system-architecture::Test suite runs from both pytest entry points`.

## 2. Extract the shared fakes

- [ ] 2.1 Create `tests/_clients.py` with the nine fake clients/runtimes; import
      them from there in every consuming test.

## 3. Fix the import path

- [ ] 3.1 Add `tests/__init__.py` (and/or set `pythonpath = ["src", "."]`) so the
      `tests` package resolves from both entry points; update the `Makefile`
      `test` target and README accordingly.

## 4. Split the test file to mirror the stage packages

- [ ] 4.1 Split `test_composition.py` into `test_composition_discovery.py`,
      `_quota.py`, `_access.py`, `_runtime.py`, `_apply.py`, moving each
      `@pytest.mark.spec` marker with its test.
- [ ] 4.2 Confirm `test_spec_coverage.py` is green — every previously bound
      scenario is still bound after the move (no marker dropped).

## 5. Close out

- [ ] 5.1 `make check` clean.
- [ ] 5.2 Run `pytest` and `python -m pytest` to full pass; identical results.
- [ ] 5.3 Remove the three bound scenarios from `tests/spec_coverage_pending.txt`
      and `EXPECTED_ACTIVE_PENDING`.
- [ ] 5.4 `openspec validate refactor-extract-test-fakes --strict`.
