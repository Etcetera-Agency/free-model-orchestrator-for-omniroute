# Change: Wire Hermes inventory as the production role/demand source

## Why

`src/fmo/hermes_inventory.py` (404 lines: real parsers for `cron/jobs.json`,
`webhook_subscriptions.json`, `hermes profile list`, `state.db` sessions, plus
the Inspector forecast) is **imported by no production module**. The composition
reads only the cron string from config (`composition.py:118`). Roles in
`_allocation_stage` are read straight from the `roles` table, but nothing in the
production pipeline populates roles, consumers, or demand signal from Hermes.

This leaves the role registry and demand source disconnected, and the third
mandated Instructor site (the Hermes Inspector forecast) unreachable in
production.

This slice adds a production stage that gathers the Hermes inventory
deterministically and feeds roles, consumers, and observed cadence into the
pipeline ahead of forecasting/allocation, with the Inspector running as a
prompt-only demand estimate over the shared runtime.

## What Changes

- Add a `hermes-inventory` production stage (ordered before `role-scoring`)
  driving the existing deterministic adapters (filesystem/command/http) selected
  by `HERMES_INVENTORY_MODE`, persisting roles, consumers, schedules, and
  observed `calls_per_run`.
- Run the Inspector forecast (`run_inspector`) over the shared runtime
  (`wire-llm-instructor-runtime`) as a prompt-only demand estimate; deterministic
  gathering owns all inventory facts, the Inspector never inspects sources.
- Refresh forecast inputs when a schedule changes (change-driven refresh).
- Fail closed on missing required Hermes env; unknown roles bootstrap through the
  existing dynamic-role path.
- Add tests for deterministic gathering, mode adapters, Inspector scope limits,
  and that allocation consumes Hermes-derived demand rather than only static
  `expected_load`.

## Impact

- Affected specs: `hermes-inventory`, `pipeline-orchestration`.
- Affected code: `src/fmo/composition.py`, `src/fmo/hermes_inventory.py`,
  `src/fmo/persistence.py`, `src/fmo/pipeline.py` (stage order), `tests/`.
- Depends on: `wire-llm-instructor-runtime` (Inspector runtime),
  `wire-scoring-allocation-stages` (allocation consumes demand).
