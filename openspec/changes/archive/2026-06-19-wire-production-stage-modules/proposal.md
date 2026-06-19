# Change: Wire production stage modules

## Why

Review found that the composed production runtime records successful runs while
most canonical stages are placeholder success functions. This lets `full`,
`scan-providers`, `research-quotas`, `probe-models`, `allocate`, `diff`,
`apply`, and related commands return green exits without invoking their domain
modules.

The current specs already say the runner must be driven by existing stage
modules, but the executable tests only prove stage names/order and metadata sync.
This change makes the production composition testable at the domain boundary so
no placeholder stage can satisfy the spec.

## What Changes

- Replace placeholder production stages with adapters around the existing domain
  modules for discovery, registry sync, quota research/classification, probing,
  telemetry/quota sync, scoring, allocation, diff/apply, and audit.
- Fix command-to-stage mapping so `sync-free-registry` invokes the free registry
  sync path and `scan-providers` invokes the OmniRoute catalog scanner path.
- Add executable tests that fail when a composed stage returns unconditional
  success without calling its domain adapter.
- Preserve fail-closed behavior: missing config, external dependency failures,
  partial/stale payloads, unsafe apply preconditions, and apply rollback failures
  map to the existing exit codes.
- Keep `/api/combos/test` forbidden.

## Impact

- Affected specs: `runtime-bootstrap`, `pipeline-orchestration`,
  `cli-and-operations`.
- Affected code: `src/fmo/composition.py`, `src/fmo/cli.py`, stage modules under
  `src/fmo/`, repository calls under `src/fmo/persistence.py`, tests under
  `tests/`.
- No new external service contract. Existing OmniRoute and repository
  boundaries are used.
