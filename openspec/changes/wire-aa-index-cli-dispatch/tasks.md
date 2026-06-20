# Implementation Tasks

## 1. TDD Coverage

- [ ] 1.1 Add a failing test: each `aa-index` subcommand routes to the migration
  handler instead of the default no-op result.
- [ ] 1.2 Add a failing test: `analyze`/`proposal` calls `run_migration_agent`
  over the shared runtime and persists an advisory threshold proposal.
- [ ] 1.3 Add a failing test: `approve`/`rollout`/`rollback` are deterministic and
  honor freeze-on-version-change and smoke-fail rollback.
- [ ] 1.4 Add a failing test: AA fetch failure and missing migration model map to
  the documented exit codes without mutating combos.
- [ ] 1.5 Bind scenarios with `@pytest.mark.spec(...)` and stage them in
  `tests/spec_coverage_pending.txt` until their tests land.

## 2. Implementation

- [ ] 2.1 Add an `aa-index` dispatch branch in `run_cli` with an injected handler.
- [ ] 2.2 Implement the handler routing each subcommand to the migration
  capability; drive `run_migration_agent` for the advisory proposal step.
- [ ] 2.3 Persist proposal/approval/rollout state through the repository and map
  outcomes to exit codes.

## 3. Verification

- [ ] 3.1 Run targeted tests: cli, aa_migration, composition.
- [ ] 3.2 Run `.venv/bin/python -m pytest -q`.
- [ ] 3.3 Run `npx --yes @fission-ai/openspec@latest validate --all --strict`.
- [ ] 3.4 Use Code Simplifier before finishing.
- [ ] 3.5 Update `completion.review` and shrink `tests/spec_coverage_pending.txt`.
