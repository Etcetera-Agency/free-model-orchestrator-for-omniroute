# Status: IMPLEMENTED

Allocation implemented with TDD in `tests/test_allocation.py`.

- Demand forecast aggregates agent-role bindings, expands shared-role DAGs, rejects cycles, computes protected demand, applies historical reserve once, and cold-starts nonzero demand.
- Allocator globally assigns capacity, avoids full double-promise, separates heavy role primaries, builds priority combos without weights, blocks oversubscription, and preserves stable order under small drift.
- Combo applier manages only `fmo-` combos, checks current state hash, snapshots, applies, smoke-tests, rolls back on failure, and raises drift conflicts.
- Audit records before/after/reasons/sources and rollback restores combo snapshots while leaving catalog snapshots intact.

Verification:

- `.venv/bin/python -m pytest tests/test_allocation.py tests/test_scoring.py tests/test_quota.py tests/test_discovery.py tests/test_foundation.py -q`
- `/Users/theDay/.nvm/versions/node/v24.1.0/bin/openspec validate add-allocation --strict`
