# Implementation Tasks

## 1. TDD Coverage

- [ ] 1.1 Add a failing test: `refine_global_tokens_per_request` aggregates
  `observed_tokens / observed_requests` across observations into the new factor;
  returns `current` unchanged when total observed requests `< min_total_requests`
  and on empty input. *(landed in `tests/test_quota_normalize.py`)*
- [ ] 1.2 Add a failing test: the refined factor is clamped to within
  `±max_change_ratio` of `current` for both an extreme downward and an extreme
  upward week. *(landed)*
- [ ] 1.3 Add a failing test: `recompute_derived_capacities` recomputes req/day
  for `summary` and `calibrated` endpoints under the new factor and omits `live`
  endpoints entirely. *(landed)*
- [ ] 1.4 Add a failing test: `tokens_per_request_recalibration_cron` is validated
  as a 5-field cron and rejected when malformed. *(config validation)*
- [ ] 1.5 Add a failing test for the weekly job: on a non-matching timestamp it is
  a no-op; on a matching timestamp it loads observations + current factor, persists
  the refined factor, recomputes only derived endpoints, and persists their
  capacities — all under one transaction.
- [ ] 1.6 Add a failing test: the job acquires its run lock and is a no-op (no
  factor write, no recompute) when the lock is already held.
- [ ] 1.7 Bind scenarios with `@pytest.mark.spec(...)` and stage them in
  `tests/spec_coverage_pending.txt` until their tests land.

## 2. Implementation

- [ ] 2.1 `quota_normalize.refine_global_tokens_per_request` + `CalibrationObservation`
  + `recompute_derived_capacities` + `DERIVED_SOURCES`. *(landed)*
- [ ] 2.2 `config.tokens_per_request_recalibration_cron` setting + cron validation.
  *(landed)*
- [ ] 2.3 Persistence: read accumulated calibration observations
  (`observed_tokens`, `observed_requests` per provider) and the current global
  factor; write the refined factor and the recomputed derived-endpoint capacities.
- [ ] 2.4 Weekly recalibration job: cron-gated tick that, under a run lock and a
  single transaction, loads observations + current factor, calls
  `refine_global_tokens_per_request`, persists the factor, calls
  `recompute_derived_capacities` over `summary`/`calibrated` endpoints, and
  persists the result; `live` endpoints untouched.
- [ ] 2.5 Wire the job's cron from `tokens_per_request_recalibration_cron` into the
  scheduler tick path alongside the daily run.

## 3. Verification

- [ ] 3.1 Run targeted tests: `test_quota_normalize.py`, config, scheduler.
- [ ] 3.2 Run `.venv/bin/python -m pytest -q`.
- [ ] 3.3 Run `npx --yes @fission-ai/openspec@latest validate add-weekly-tpr-recalibration --strict`.
- [ ] 3.4 Use Code Simplifier before finishing.
- [ ] 3.5 Update `completion.review` and shrink `tests/spec_coverage_pending.txt`.
