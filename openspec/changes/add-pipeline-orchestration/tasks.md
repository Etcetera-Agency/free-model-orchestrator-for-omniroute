## 1. Run record and stage registry

- [ ] 1.1 Failing test: starting a run creates one persisted run record with a run id
- [ ] 1.2 Implement run record creation/load via the repository layer
- [ ] 1.3 Failing test: stages execute in the canonical order and each records a status
- [ ] 1.4 Implement ordered stage registry composing existing stage modules

## 2. Idempotent skip

- [ ] 2.1 Failing test: re-running with an unchanged stage idempotency key skips re-execution
- [ ] 2.2 Implement idempotency check that reads prior stage result before running

## 3. Fail-closed gating

- [ ] 3.1 Failing test: a failed safety gate stops downstream apply
- [ ] 3.2 Failing test: partial/stale stage output is not consumed by dependent stages
- [ ] 3.3 Failing test: the runner never calls `/api/combos/test`
- [ ] 3.4 Implement stop-on-gate and partial/stale propagation

## 4. Exit-code mapping

- [ ] 4.1 Failing tests: run outcomes map to 0 / 2 / 3 / 4 / 5 / 6 / 7
- [ ] 4.2 Implement the shared outcome→exit-code mapping table

## 5. Validation

- [ ] 5.1 Run targeted pytest for `tests/test_pipeline.py`
- [ ] 5.2 Run full `pytest -q`
- [ ] 5.3 `openspec validate add-pipeline-orchestration --strict`
