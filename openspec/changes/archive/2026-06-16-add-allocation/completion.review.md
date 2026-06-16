# Completion Review: add-allocation

Completion of P1: 100%* — demand sums agent-role bindings, expands shared role dependencies, and rejects cycles.
Completion of P2: 100%* — protected demand uses max(p95, expected×peak) and historical reserve records base/multiplier/reserved exactly once.
Completion of P3: 100%* — cold start chooses nonzero demand from schedule/bootstrap/role/global priority.
Completion of P4: 100%* — global allocation tracks pool usage and separates heavy-role primaries.
Completion of P5: 100%* — combo builder emits one ordered priority list per role without weights.
Completion of P6: 100%* — oversubscription blocks apply and missing primary degrades instead of using paid fallback.
Completion of P7: 100%* — sub-threshold drift keeps existing combo order.
Completion of P8: 100%* — applier manages only `fmo-` combos and checks hash/snapshot/apply/smoke path.
Completion of P9: 100%* — smoke failure restores snapshot and drift raises conflict instead of overwrite.
Completion of P10: 100%* — audit log records before/after/reason/source refs and rollback preserves catalog snapshots.

Code Simplifier:

- Ran simplification pass on touched allocation code.
- Kept demand, allocation, applier, and audit as small deterministic modules.

Verification:

- `.venv/bin/python -m pytest tests/test_allocation.py tests/test_scoring.py tests/test_quota.py tests/test_discovery.py tests/test_foundation.py -q` — 42 passed.
- `openspec validate add-allocation --strict` — valid.
