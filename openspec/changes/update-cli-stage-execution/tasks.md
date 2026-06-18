## 1. Per-stage command dispatch

- [ ] 1.1 Failing test: `scan-providers`/`match-models`/`probe-models`/`score-roles`/`allocate`/`diff` each invoke their pipeline stage via the runner
- [ ] 1.2 Implement command→stage dispatch in `run_cli`
- [ ] 1.3 Failing test: a stage failure surfaces the runner's exit code (not unconditional 0)

## 2. Guarded apply / rollback

- [ ] 2.1 Failing tests: `apply` returns 5 when unsafe, 6 on apply-failed-rolled-back, 7 on rollback-failed
- [ ] 2.2 Implement `apply`/`rollback` through the runner's fail-closed gating
- [ ] 2.3 Failing test: `--dry-run` validates locally and never calls `/api/combos/test`

## 3. Diagnostics

- [ ] 3.1 Failing tests: `explain-endpoint`/`explain-role` print real persisted score components and selection rationale
- [ ] 3.2 Implement diagnostics reading through the repository layer

## 4. Validation

- [ ] 4.1 Run targeted pytest for `tests/test_cli.py`
- [ ] 4.2 Run full `pytest -q`
- [ ] 4.3 `openspec validate update-cli-stage-execution --strict`
