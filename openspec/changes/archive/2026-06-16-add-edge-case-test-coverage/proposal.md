# add-edge-case-test-coverage

## Why

Current implementation has solid happy-path and simulated E2E coverage, but
several branch-level behaviors remain unpinned. These gaps are mostly negative
paths: retry exhaustion, malformed config, fail-closed access classification,
edge allocation constraints, advisory diff validation, token false positives,
secret redaction, state transition guards, scanner removal guards, and probe
error mapping.

Without explicit tests, later refactors can silently widen apply permissions,
sleep on bad `Retry-After`, treat unknown quota as usable, allocate unstable
combos, leak prompt secrets, or promote endpoints from weak signals.

## What Changes

- Add regression requirements for edge-case tests across:
  `omniroute-client`, `environment-and-connections`, `access-classifier`,
  `role-scorer`, `quota-manager`, `allocator`, `smart-combo-reviewer`,
  `free-candidate-discovery`, `web-cookie-candidates`, `llm-runtime`,
  `data-model`, `account-discovery`, `provider-scanner`, and `probe-runner`.
- Pin each requested negative branch as an automated pytest case.
- Keep tests local and deterministic: fake HTTP/session/instructor boundaries,
  real function calls, real data objects, no live human run.
- Keep expected behavior unchanged unless a test exposes a mismatch; then fix
  implementation in the same slice and update `completion.review`.

## Pseudocode

```text
for module in requested_modules:
  read current public functions and existing tests
  add pytest cases for every listed branch
  run targeted test file
  if red due to missing behavior:
    make smallest production fix
    record fix in completion.review
  run full pytest
  run openspec validate --all --strict
```

## Impact

- Specs modified: fourteen existing capabilities gain edge-case regression
  coverage requirements.
- Code impact expected mostly in `tests/`; production code changes only if a
  requested behavior is not already implemented.
- No API shape change. No backwards-compatibility shim.
