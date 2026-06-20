# Implementation Tasks

## 1. TDD Coverage

- [x] 1.1 Add a failing effect test: `probing` runs only for `confirmed`-free
  endpoints with reserved capacity and never exceeds confirmed free capacity.
- [x] 1.2 Add a failing effect test: `probing` persists probe results and
  excludes endpoints whose probe fails.
- [x] 1.3 Add a failing effect test: `telemetry-sync` writes normalized telemetry
  rows used by scoring.
- [x] 1.4 Add a failing effect test: `quota-sync` writes synced remaining-quota
  state with correct attribution.
- [x] 1.5 Add a failing test that swapping any adapter for unconditional success
  fails the harness.
- [x] 1.6 Bind scenarios with `@pytest.mark.spec(...)` and stage them in
  `tests/spec_coverage_pending.txt` until their tests land.

## 2. Implementation

- [x] 2.1 Add a `probing` adapter calling `probes`, gated on confirmed-free +
  reserved capacity, persisting results.
- [x] 2.2 Add a `telemetry-sync` adapter calling `telemetry`, persisting
  normalized rows.
- [x] 2.3 Add a `quota-sync` adapter calling `quota_manager` +
  `quota_attribution`, persisting remaining-quota state.
- [x] 2.4 Register the three adapters in the per-stage registry so `full`
  advances past them.

## 3. Verification

- [x] 3.1 Run targeted tests for probes, telemetry, quota, composition.
- [x] 3.2 Run `.venv/bin/python -m pytest -q`.
- [x] 3.3 Run `npx --yes @fission-ai/openspec@latest validate --all --strict`.
- [x] 3.4 Use Code Simplifier before finishing.
- [x] 3.5 Update `completion.review` and shrink `tests/spec_coverage_pending.txt`.
