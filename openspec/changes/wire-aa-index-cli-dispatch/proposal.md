# Change: Wire the aa-index CLI dispatch and migration agent

## Why

The `aa-index` subcommand is parsed in `cli.py` (`status | analyze | proposal |
approve | reject | rollout | rollback`) but `run_cli` has **no branch handling
it** — control falls through to the default `CliResult(success, changed=False)`,
so every `aa-index` command is a silent no-op. Consequently the
Artificial-Analysis index-migration agent (`src/fmo/aa_migration.py`,
`run_migration_agent`) — the fourth mandated Instructor site — is implemented and
unit tested but never reachable in production.

This slice wires the subcommand to the migration capability: freezing thresholds
on a new major AA index, generating an advisory LLM threshold proposal via the
shared runtime, and driving deterministic approval/rollout/rollback.

## What Changes

- Add an `aa-index` dispatch branch in `run_cli` routing each subcommand to the
  migration capability through an injected handler (consistent with how `serve`
  and `explain-*` are dispatched).
- Drive `run_migration_agent` over the shared Instructor runtime
  (`wire-llm-instructor-runtime`) for the `analyze`/`proposal` steps; the LLM
  produces an advisory threshold proposal only.
- Keep deterministic ownership of validation, approval, rollout and rollback,
  including freeze-on-version-change and smoke-fail rollback; map outcomes to the
  documented exit codes.
- Add tests for dispatch routing, advisory proposal generation, and deterministic
  approval/rollback, including the AA-fetch-fails and no-migration-model paths.

## Impact

- Affected specs: `cli-and-operations`, `aa-index-migration`.
- Affected code: `src/fmo/cli.py`, `src/fmo/composition.py`,
  `src/fmo/aa_migration.py`, `src/fmo/persistence.py`, `tests/`.
- Depends on: `wire-llm-instructor-runtime` (shared runtime for the proposal step).
