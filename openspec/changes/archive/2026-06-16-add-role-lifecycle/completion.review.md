# Completion Review: add-role-lifecycle

Completion of P1: 100%* — all three adapters normalize samples and fail on missing required env.
Completion of P2: 100%* — inventory records agent_profile, cron_job, webhook, and service consumers with cadence/calls_per_run.
Completion of P3: 100%* — unknown role returns full inventory trigger, not partial.
Completion of P4: 100%* — inventory diff marks forecast stale, triggers Inspector, and rebuilds only on material allocation change.
Completion of P5: 100%* — deterministic prompt assembly includes consumers/changes and redacts secrets.
Completion of P6: 100%* — Inspector returns forecast fields only, no model choice or quota change.
Completion of P7: 100%* — missing role is retiring, not deleted immediately.
Completion of P8: 100%* — reappearing role reactivates and clears `missing_since`.
Completion of P9: 100%* — new role receives template policy and cold-start demand.

Code Simplifier:

- Ran simplification pass on touched role lifecycle code.
- Kept inventory normalization and role reconciliation separate and deterministic.

Verification:

- `.venv/bin/python -m pytest tests/test_role_lifecycle.py tests/test_allocation.py tests/test_scoring.py tests/test_quota.py tests/test_discovery.py tests/test_foundation.py -q` — 47 passed.
- `/Users/theDay/.nvm/versions/node/v24.1.0/bin/openspec validate add-role-lifecycle --strict` — valid.
