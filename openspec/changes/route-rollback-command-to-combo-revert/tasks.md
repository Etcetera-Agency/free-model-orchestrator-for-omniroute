## 1. Route rollback to combo revert

- [ ] 1.1 Failing test: `rollback --run-id R` reverts every applied `fmo-` combo
      of run R to its persisted pre-change state and records audit entries
- [ ] 1.2 Failing test: `rollback --endpoint E` / `--role` reverts a single combo
- [ ] 1.3 Implement the combo revert path and stop routing `rollback` to
      `_rollback_latest_aa_migration`

## 2. Exit codes and gating

- [ ] 2.1 Failing test: a failing restore call yields exit 7 (`rollback_failed`)
- [ ] 2.2 Failing test: a clean revert yields exit 0
- [ ] 2.3 Implement fail-closed gating consistent with `apply`

## 3. Keep aa-index rollback separate

- [ ] 3.1 Failing test: `aa-index rollback` still reverts the AA-index threshold
      and the top-level `rollback` does not touch AA-index state
- [ ] 3.2 Confirm no regression in `aa-index` dispatch

## 4. Validation

- [ ] 4.1 Targeted pytest for CLI rollback and audit
- [ ] 4.2 Full `pytest -q`
- [ ] 4.3 Bind tests with `@pytest.mark.spec(...)` and shrink the pending list
- [ ] 4.4 `openspec validate route-rollback-command-to-combo-revert --strict`
