# add-advisory-llm

## Why

The project has exactly four Instructor/LLM call sites. Two are core and live in
earlier phases (the quota-research inspector in `add-quota`, the Hermes role
Inspector forecast in `hermes-inventory`). This phase adds the other two. They
are fully in scope, but advisory and fail-open: if the LLM is unavailable or
returns nothing usable, the deterministic pipeline proceeds without it. They are
an advisory review of built combos, and a guarded procedure for migrating role
quality thresholds when the Artificial Analysis index version changes. Both use
the same thin Instructor runtime and never override deterministic safety. Source:
`reference/docs/modules/22,20`, `reference/docs/architecture/08`.

## What Changes

- Add `smart-combo-reviewer`: one structured Instructor call proposing only
  add/remove/move diffs, each validated independently; advisory, never blocking.
- Add `aa-index-migration`: detect index-version change, freeze old thresholds,
  keep current combos, LLM proposal via the highest-intelligence model,
  deterministic validation + dry-run + approval-gated rollout + rollback.

## Impact

- New specs: `smart-combo-reviewer`, `aa-index-migration`.
- Depends on: `add-scoring` (quality gate), `add-allocation` (combos).
- Fail-open: when these LLM steps fail or are unavailable, the deterministic plan
  remains applicable — they are part of the project, not skippable scope.
