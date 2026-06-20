# Change: Wire role-scoring, allocation, and diff stages

## Why

After probing/telemetry/quota are wired, `role-scoring`, `allocation`, and
`diff` remain unwired and stop the `full` run. Their modules
(`src/fmo/scoring.py`, `src/fmo/forecast.py`, `src/fmo/allocation.py`,
`src/fmo/applier.py` diff path) are implemented and unit tested but not imported
by production composition.

This group turns usable, capacity-verified endpoints into the per-role combo
plan: scoring ranks endpoints, demand forecast plus global allocation builds one
priority combo per role, and diff computes the minimal change against current
OmniRoute state — without yet applying it.

## What Changes

- Add production adapters driving `scoring`, `forecast` + `allocation`, and the
  `applier` diff computation from the composed runtime.
- Persist scoring output, allocation plans (`allocation_plans` rows with targets
  and constraint report), and the computed minimal diff through the repository.
- Honor allocator rules in the production path: global allocation across all
  roles, heavy-role separation, oversubscription gate, one priority combo per
  role, deterministic stable ordering, and degraded modes with no paid fallback.
- Add executable effect tests asserting plans/diffs are persisted and that
  swapping any adapter for unconditional success fails.

## Impact

- Affected specs: `pipeline-orchestration`.
- Affected code: `src/fmo/composition.py`, `src/fmo/scoring.py`,
  `src/fmo/forecast.py`, `src/fmo/allocation.py`, `src/fmo/applier.py`
  (diff path), `src/fmo/persistence.py`, `tests/`.
- Depends on: `wire-probe-telemetry-stages`.
- No new external service contract. `diff` reads but does not mutate OmniRoute.
