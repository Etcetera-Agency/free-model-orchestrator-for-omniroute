# Code analysis & refactoring plan

Generated 2026-06-23. Re-run the numbers with `make analysis`.

## Toolchain (now configured)

All config lives in `pyproject.toml`; convenience targets in `Makefile`.

| Tool | Purpose | Invoke | Baseline |
|------|---------|--------|----------|
| **ruff** (lint) | correctness, imports, modernization, simplify | `make lint` | 130 issues, 113 auto-fixable |
| **ruff** (format) | deterministic formatting | `make format` | 33 / 84 files would reformat |
| **pyright** | static type checking (basic, py3.12) | `make typecheck` | 66 errors, 2 warnings |
| **vulture** | dead-code detection (≥80% conf) | `make deadcode` | clean (3 false positives whitelisted) |
| **pytest** | test suite | `make test` | 449 passed, 2 deselected (~4m25s) |

`make check` runs every non-mutating gate; `make fix` applies ruff lint + format.

## Findings

### 1. Dead code — essentially none
Vulture at ≥80% confidence finds only three names, all **unused parameters kept
for signature stability** (`thresholds`, `model_endpoint_check`, `daily_refresh`),
recorded in `whitelist.py`. No dead functions/classes/modules. This is a healthy
codebase; the "dead code" axis needs no removal work, only the whitelist + the
`ARG001` ruff rule to keep it that way. Decide per-parameter: prefix with `_` if
truly vestigial, or keep whitelisted if part of a stable interface.

### 2. Lint/format — mostly mechanical (do first, low risk)
113 of 130 ruff issues are auto-fixable: unsorted imports (38), `datetime.utc`
modernization (47), unused imports (17), deprecated imports (4). Run `make fix`,
then eyeball the 17 non-auto items (`B904` raise-from, `PLW0108` lambda,
`UP042` str-enum). **Do this before any structural refactor** so diffs stay clean.

### 3. Type errors — 66 real ones
Now visible because pyright was previously defaulting to py3.9 (200+ spurious
union-syntax errors). The remaining 66 are genuine: `Unknown | None` passed where
`str` is required (e.g. `web_cookie.py:126`), missing narrowing. Triage after the
lint pass; many cluster in `web_cookie.py`, `telemetry.py`.

### 4. File splitting — two clear god-modules
- **`composition_stages.py` (2239 lines, ~70 top-level defs)** is the priority.
  It mixes every pipeline stage + their private helpers in one file. Split into a
  `composition_stages/` package by stage domain, keeping a thin re-export shim so
  imports don't break:
  - `discovery.py` — metadata, free-candidate, account-discovery, catalog scan
  - `quota.py` — quota research / sync / hints / pools (`_ensure_*_quota_pool`)
  - `access.py` — access classification, lost-access state
  - `probing.py`, `telemetry.py`
  - `inventory.py` — hermes inventory read/inspect
  - `roles.py` — role lifecycle, scoring, quality bands, health/latency components
  - `allocation.py` — demand forecast, allocation, router input
  - `apply.py` — diff, review, apply, rollback, audit, snapshots, safety checks
  - `_helpers.py` — `_canonical_slug`, `_hash_parts`, `_quota_metric`, etc.
- **`persistence.py` (1240 lines, 16 repository classes)** splits cleanly into a
  `persistence/` package — one module per aggregate (run, provider, account,
  catalog, registry, endpoint, snapshot, quota, probe, role, score, allocation,
  combo, audit, external-metadata) over a shared `_base.py` (`Database`,
  `Repository`, `_one/_optional/_many/_jsonb`). Re-export from `__init__.py`.

### 5. Unification opportunities
- Repeated row-helpers (`_one/_optional/_many/_jsonb/_content_hash`) appear in
  `persistence.py` and ad-hoc in stages — centralize in `persistence/_base.py`.
- `datetime.now(timezone.utc)` patterns (47 hits) → one `utcnow()` helper after
  the `UP017` fix.
- `_canonical_slug` / `_hash_parts` / idempotency-key builders are scattered;
  consolidate into the existing `idempotency.py`.
- Quota math (`_quota_metric`, `_quota_limit`, `_remaining_amount`) lives in
  stages but belongs next to `quota_normalize.py` / `quota_manager.py`.

### 6. Test refactoring
- **`test_composition.py` (3142 lines, 85 tests, 9 fake clients).** The fakes
  (`QuotaSearchClient`, `PipelineOpsClient`, `FakeOpenAIClient`, …) are shared
  infra living inside the test file. Extract them to `tests/_clients.py` (next to
  the existing `tests/_fixtures.py` / `tests/_stage_effects.py`), then split the
  tests to mirror the new stage packages (`test_composition_quota.py`,
  `_access.py`, `_apply.py`, …). 134 `@pytest.mark.spec` markers must move with
  their tests — the `test_spec_coverage.py` gate will catch any that get dropped.
- **Import-path fragility (worth fixing).** The suite only runs via
  `python -m pytest`; the bare `pytest` console script fails with
  `ModuleNotFoundError: No module named 'tests'` because cwd isn't on `sys.path`.
  Add `tests/__init__.py` (or set `pythonpath = ["src", "."]`) so both entry
  points work and the `make test` target is robust.

## Suggested order
1. `make fix` (lint + format) — mechanical, review the 17 manual lint items.
2. Fix the test import-path so `make test` runs either way.
3. Type-error triage (66) — independent, can parallelize.
4. Split `persistence.py` (simpler, class-per-file) — proves the shim pattern.
5. Split `composition_stages.py` — the big one.
6. Extract test fakes + split `test_composition.py` to match.
7. Unification passes (5) as cleanup once boundaries exist.

Each step keeps `make check` + `make test` green before moving on.
