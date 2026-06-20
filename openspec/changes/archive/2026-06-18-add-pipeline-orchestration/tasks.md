## 1. Run record and stage registry

- [x] 1.1 Failing test: starting a run creates one persisted run record with a run id
- [x] 1.2 Implement run record creation/load via the repository layer
- [x] 1.3 Failing test: stages execute in the canonical order and each records a status
- [x] 1.4 Implement ordered stage registry composing existing stage modules

## 2. Idempotent skip

- [x] 2.1 Failing test: re-running with an unchanged stage idempotency key skips re-execution
- [x] 2.2 Implement idempotency check that reads prior stage result before running

## 3. Fail-closed gating

- [x] 3.1 Failing test: a failed safety gate stops downstream apply
- [x] 3.2 Failing test: partial/stale stage output is not consumed by dependent stages
- [x] 3.3 Failing test: the runner never calls `/api/combos/test`
- [x] 3.4 Implement stop-on-gate and partial/stale propagation

## 4. Exit-code mapping

- [x] 4.1 Failing tests: run outcomes map to 0 / 2 / 3 / 4 / 5 / 6 / 7
- [x] 4.2 Implement the shared outcome→exit-code mapping table

## 5. Validation

- [x] 5.1 Run targeted pytest for `tests/test_pipeline.py`
- [x] 5.2 Run full `pytest -q`
- [x] 5.3 `openspec validate add-pipeline-orchestration --strict`
