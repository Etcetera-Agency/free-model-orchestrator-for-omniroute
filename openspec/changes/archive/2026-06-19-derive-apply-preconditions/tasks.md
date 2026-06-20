## 1. Evaluate the apply guard at the entrypoint

- [x] 1.1 Failing test: the real entrypoint (no injected dispatcher) computes preconditions from the apply guard, not a hardcoded `True`
- [x] 1.2 Implement `bootstrap_and_dispatch` to evaluate `apply_guard` (DB availability, saved snapshot, valid desired state, quota safety, probe/smoke pass) and pass the result into dispatch

## 2. Fail closed

- [x] 2.1 Failing test: a failing/unknown/stale guard input yields preconditions `False` and `apply` exits 5 with no change
- [x] 2.2 Failing test: all guard inputs healthy yields preconditions `True` and `apply` is allowed to proceed
- [x] 2.3 Implement conservative (fail-closed) precondition derivation

## 3. Validation

- [x] 3.1 Run targeted pytest for `tests/test_bootstrap.py` and `tests/test_cli.py`
- [x] 3.2 Run full `pytest -q`
- [x] 3.3 `openspec validate derive-apply-preconditions --strict`
