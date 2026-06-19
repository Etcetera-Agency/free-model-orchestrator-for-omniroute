# Change: Derive apply preconditions from the apply guard

## Why

`runtime-bootstrap::Real service entrypoint` already requires that apply
preconditions be "derived from startup validation, not from a hardcoded value".
The production entrypoint violates this: `bootstrap_and_dispatch` ends with
`return dispatcher(list(argv), True)` — `preconditions_ok` is the literal `True`.
`src/fmo/apply_guard.py` is never imported by `bootstrap.py` or `cli.py`. As a
result `apply` can never return `unsafe_to_apply` (exit 5) from a real safety
evaluation; the central README guarantee ("Apply is guarded by DB availability,
saved snapshot, valid desired state, quota safety, and passing smoke/probe
checks") is not enforced on the real path. The existing entrypoint test only
passes because it injects a stub dispatcher and never exercises the guard.

## What Changes

- The entrypoint computes `preconditions_ok` by evaluating the apply guard:
  database availability, a saved snapshot exists, the desired state is valid,
  quota safety holds, and the latest probe/smoke result passed.
- Fail closed: if any input is unknown, stale, or unavailable, preconditions are
  `False`.
- Pass the computed boolean (not `True`) into the CLI dispatch so `apply` exits 5
  when unsafe and changes nothing.
- Add a test that drives the **real** entrypoint (no injected dispatcher) with a
  failing guard input and asserts exit 5 / no change, and a passing-guard case
  that allows apply.

## Impact

- Affected specs: `combo-applier` (ADDED: entrypoint precondition gate).
- Affected code: `src/fmo/bootstrap.py` (`bootstrap_and_dispatch`), consuming
  `src/fmo/apply_guard.py` and the repository layer.
- Depends on `compose-production-pipeline` (shared composition root) and
  `add-persistence-repositories`.
