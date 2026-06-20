## 1. Scheduler entrypoint

- [x] 1.1 Failing test: a `serve` entrypoint starts a full run when the configured cron time arrives, through the composed runner
- [x] 1.2 Implement the long-running scheduler entrypoint owning the `HERMES_INVENTORY_CRON` loop
- [x] 1.3 Failing test: the scheduler never calls `/api/combos/test`

## 2. Run-lock enforcement end-to-end

- [x] 2.1 Failing test (`scheduler::Overlapping daily runs`): a second start while the daily lock is held does not begin a concurrent run
- [x] 2.2 Failing test (`scheduler::Urgent run after paid charge`): an urgent trigger starts an out-of-schedule run subject to the run-lock
- [x] 2.3 Implement trigger routing (cron, manual, event-driven, urgent) through the persistent run-lock

## 3. Shrink the allowlist

- [x] 3.1 Bind `scheduler::Scheduled daily run`, `scheduler::Overlapping daily runs`, `scheduler::Urgent run after paid charge` with `@pytest.mark.spec(...)`
- [x] 3.2 Remove those three lines from `tests/spec_coverage_pending.txt`

## 4. Validation

- [x] 4.1 Run targeted pytest for `tests/test_scheduler.py`
- [x] 4.2 Run full `pytest -q` (includes the executable-spec coverage gate)
- [x] 4.3 `openspec validate run-scheduler-process --strict`
