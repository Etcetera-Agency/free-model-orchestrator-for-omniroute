# Change: Wire apply and audit stages with real combo smoke test

## Why

`apply` and `audit` are the final unwired stages. After the scoring/allocation
slice, a plan and diff exist but nothing is applied to OmniRoute. In the current
composition `apply` routes through the no-op adapter, and `_cli_result`
hardcodes `combo_test_called=False`, so the production path never invokes the
applier, the apply guard, the transactional smoke test, or rollback. The
`combo-applier` and `audit-rollback` modules (`src/fmo/applier.py`,
`src/fmo/apply_guard.py`, `src/fmo/audit.py`) are implemented and unit tested but
unused by production.

This slice closes the loop so a `full` run actually applies minimal diffs to
OmniRoute, smoke-tests them, audits the result, and rolls back on failure —
honoring exit codes 5 (`unsafe_to_apply`), 6 (`apply_failed_rolled_back`), and 7
(`rollback_failed`).

## What Changes

- Add production adapters driving `applier` (apply path), `apply_guard`, and
  `audit` from the composed runtime, using repository-backed preconditions.
- Run the transactional apply with a real combo smoke test and stop applying
  `fmo-` combos when guard inputs fail; never call `/api/combos/test`.
- Replace the hardcoded `combo_test_called=False` in `_cli_result` with the real
  signal from the apply adapter.
- On smoke-test failure, roll back and map to `apply_failed_rolled_back`; on
  failed rollback map to `rollback_failed`; on failing guard input map to
  `unsafe_to_apply`.
- Persist audit records and snapshots; record drift/anti-churn protection so a
  manually edited combo is detected.
- Add executable effect tests asserting the applier and smoke test are invoked,
  rollback fires on failure, and swapping any adapter for unconditional success
  fails.

## Impact

- Affected specs: `pipeline-orchestration`, `combo-applier`.
- Affected code: `src/fmo/composition.py` (`_cli_result`, adapters),
  `src/fmo/cli.py`, `src/fmo/applier.py`, `src/fmo/apply_guard.py`,
  `src/fmo/audit.py`, `src/fmo/persistence.py`, `tests/`.
- Depends on: `wire-scoring-allocation-stages`.
- No new external service contract; apply uses the existing OmniRoute management
  API and the existing smoke-test path (never `/api/combos/test`).
