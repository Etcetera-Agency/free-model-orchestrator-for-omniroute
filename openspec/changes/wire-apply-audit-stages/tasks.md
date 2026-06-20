# Implementation Tasks

## 1. TDD Coverage

- [ ] 1.1 Add a failing effect test: production `apply` invokes the applier and a
  real transactional combo smoke test, mutating only `fmo-` combos.
- [ ] 1.2 Add a failing test: `_cli_result.combo_test_called` reflects the real
  apply-adapter signal (no longer hardcoded `False`).
- [ ] 1.3 Add a failing test: failing guard input returns `unsafe_to_apply` (5)
  and apply does not mutate OmniRoute.
- [ ] 1.4 Add a failing test: smoke-test failure rolls back and returns
  `apply_failed_rolled_back` (6); failed rollback returns `rollback_failed` (7).
- [ ] 1.5 Add a failing test: `audit` persists audit records and snapshots and
  detects a manually edited combo (drift / anti-churn).
- [ ] 1.6 Add a failing test that `/api/combos/test` is never called and that
  swapping the apply/audit adapter for unconditional success fails the harness.
- [ ] 1.7 Bind scenarios with `@pytest.mark.spec(...)` and stage them in
  `tests/spec_coverage_pending.txt` until their tests land.

## 2. Implementation

- [ ] 2.1 Add an `apply` adapter calling `apply_guard` + `applier` with a real
  transactional smoke test, restricted to `fmo-` combos.
- [ ] 2.2 Replace hardcoded `combo_test_called=False` in `_cli_result` with the
  apply-adapter signal.
- [ ] 2.3 Map guard/apply/rollback outcomes to exit codes 5/6/7.
- [ ] 2.4 Add an `audit` adapter calling `audit`, persisting records, snapshots,
  and drift/anti-churn protection.
- [ ] 2.5 Register both adapters so `full` runs end to end.

## 3. Verification

- [ ] 3.1 Run targeted tests for applier, apply_guard, audit, composition, cli.
- [ ] 3.2 Run `.venv/bin/python -m pytest -q`.
- [ ] 3.3 Run `npx --yes @fission-ai/openspec@latest validate --all --strict`.
- [ ] 3.4 Use Code Simplifier before finishing.
- [ ] 3.5 Update `completion.review` to state the full pipeline now applies and
  audits end to end; empty `tests/spec_coverage_pending.txt`.
