# add-scoring

## Why

Once endpoints are discovered and confirmed free, the orchestrator must verify
they work, learn their stability/latency, and rank them per role under hard
eligibility filters (context, quality gate). Source:
`reference/docs/modules/06,07,09`, `reference/docs/architecture/07`.

## What Changes

- Add `probe-runner`: free-gated probing, dedicated provider route, capability
  suites, retry/error handling, promotion to active.
- Add `telemetry-sync`: daily OmniRoute telemetry, latency-granularity honesty,
  degradation rules.
- Add `role-scorer`: eligibility filter, additive score, AA scoring v1
  (normalization + missing-metric redistribution), latency source priority,
  immutable scores by input_state_hash.
- Add `context-window-eligibility`: per-endpoint effective context, hard
  minimum filter, one combo per role, unknown excluded.
- Add `quality-gate`: at most one quality gate per role (a role may omit it) as a
  hard filter, unverifiable handling, index-version binding.

## Impact

- New specs: `probe-runner`, `telemetry-sync`, `role-scorer`,
  `context-window-eligibility`, `quality-gate`.
- Depends on: `add-foundation`, `add-discovery`, `add-quota`.
- Feeds: allocation.
