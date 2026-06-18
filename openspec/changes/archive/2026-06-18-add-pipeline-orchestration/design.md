## Context

The stage modules already exist and are unit-tested in isolation. The missing
piece is a deterministic driver that owns ordering, run state, idempotency
skipping, fail-closed gating and exit-code mapping. The runner must not
re-implement stage logic — it composes the existing functions.

## Goals / Non-Goals

- Goals: one ordered run; persisted run + per-stage status; idempotent skip;
  fail-closed gating; exit-code mapping; no `/api/combos/test`.
- Non-Goals: scheduling/cron (in `add-runtime-bootstrap-and-locks`); changing
  any stage's internal algorithm; new external integrations.

## Decisions

- Decision: stage registry is an ordered list of callables, each taking a run
  context (run id, db repositories, config) and returning a stage result with a
  status in `{ok, partial_stale, validation_failed, external_dependency_failed,
  unsafe, applied, rolled_back}`. The runner stops at the first status that
  forbids continuing and maps the worst status to the process exit code.
- Decision: idempotency is checked by reading the stage's prior result for the
  same idempotency key from the repository; an unchanged key skips re-execution.
- Alternatives considered: an event/queue framework — rejected (YAGNI; the
  process runs once per day).

## Risks / Trade-offs

- Risk: a stage partially writes then fails → mitigated by per-stage transaction
  boundaries from `persistence`.
- Risk: exit-code mapping drifts from `cli-and-operations` → single mapping table
  shared with the CLI slice.

## Migration Plan

Additive. `cli.py` keeps working until `update-cli-stage-execution` wires
commands to the runner.

## Open Questions

- None blocking; allocation/apply gate details already covered by existing specs.
