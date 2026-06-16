# Status: IMPLEMENTED

Role lifecycle implemented with TDD in `tests/test_role_lifecycle.py`.

- Filesystem, command, and HTTP inventory adapters normalize to one internal consumer schema and fail on missing env.
- Inventory records agent profiles, cron jobs, webhooks, and services with cadence and calls per run.
- Unknown role detection triggers full inventory.
- Inventory diffs mark forecasts stale and gate combo rebuilds on material allocation changes.
- Deterministic prompt assembly gathers inventory/diff data and redacts secrets before Inspector call.
- Inspector returns forecast-only structured data with no model choice or quota changes.
- Role reconciliation retires missing roles with grace, reactivates reappearing roles, and bootstraps new roles.

Verification:

- `.venv/bin/python -m pytest tests/test_role_lifecycle.py tests/test_allocation.py tests/test_scoring.py tests/test_quota.py tests/test_discovery.py tests/test_foundation.py -q`
- `/Users/theDay/.nvm/versions/node/v24.1.0/bin/openspec validate add-role-lifecycle --strict`
