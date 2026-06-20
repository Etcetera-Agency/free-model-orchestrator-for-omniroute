# Change: Wire model-matching, quota-research, and access-classification stages

## Why

After `fix-stage-effect-contract`, the `model-matching`, `quota-research`, and
`access-classification` canonical stages return `not_implemented` and stop the
`full` run. Their domain modules (`src/fmo/matcher.py`, `src/fmo/quota_research.py`,
`src/fmo/access.py`, `src/fmo/quota_attribution.py`) are implemented and unit
tested but are not imported by production composition.

These three stages are the first dependent group after discovery: matching binds
free candidates to OmniRoute provider endpoints, quota-research extracts quota
bounds, and access-classification produces the `confirmed | inferred |
assumed_shared | unknown` status that every later capacity decision relies on.

## What Changes

- Add production adapters that drive `matcher`, `quota_research`, and `access`
  (with `quota_attribution`) from the composed runtime, using the repository and
  OmniRoute client in `StageDependencies`.
- Persist each stage's real output through the repository: matched endpoints,
  quota-research snapshots/rules, and access-classification status with its
  evidence and confidence cap.
- Honor fail-closed rules: a missing or stale external payload maps to
  `external_dependency_failed` / `partial_stale`; summary-sourced quota rules are
  capped by `summary_confidence_cap`; unknown access never becomes free.
- Add executable effect tests (via the slice-1 harness) asserting the real rows
  are written and that swapping any adapter for unconditional success fails.

## Impact

- Affected specs: `pipeline-orchestration`.
- Affected code: `src/fmo/composition.py`, `src/fmo/matcher.py`,
  `src/fmo/quota_research.py`, `src/fmo/access.py`,
  `src/fmo/quota_attribution.py`, `src/fmo/persistence.py`, `tests/`.
- Depends on: `fix-stage-effect-contract`.
- No new external service contract.
