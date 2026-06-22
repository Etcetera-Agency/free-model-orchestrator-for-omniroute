# Implementation Tasks

## 1. TDD Coverage

- [ ] 1.1 Add a failing test: an endpoint with a `tokens/month` live budget and a
  `requests/day` research limit yields one capacity in req/day equal to the tighter
  converted axis (via `binding_capacity`).
- [ ] 1.2 Add a failing test: live quota `quotaTotal`/`quotaUsed` is treated as the
  `tokens` axis and converted to req/day; `remaining` is derived in req/day.
- [ ] 1.3 Add a failing test: a self-calibrated no-auth `tokens` rule is included in
  the endpoint's axes and contributes its converted capacity.
- [ ] 1.4 Add a failing test: `effective_remaining` stays unknown when every source
  is unknown, and a negative result (reservations + buffer exceed remaining) is
  preserved — now in req/day.
- [ ] 1.5 Add a failing test: a sub-day request axis present on the endpoint is
  excluded from the binding capacity.
- [ ] 1.6 Bind scenarios with `@pytest.mark.spec(...)` and stage them in
  `tests/spec_coverage_pending.txt` until their tests land.

## 2. Implementation

- [ ] 2.1 Assemble each endpoint's known budget axes from its research rule,
  no-auth calibration rule and live quota into a list of `(metric, window, amount)`.
- [ ] 2.2 Convert that list with `binding_capacity` (factor `tokens_per_request`)
  into one req/day capacity bound by the tightest axis.
- [ ] 2.3 Treat live `quotaTotal`/`quotaUsed` as the `tokens` axis; derive
  `remaining` in req/day from the converted limit.
- [ ] 2.4 Compute `effective_remaining` in req/day from the converted limit,
  provider remaining, local usage, pending reservations and safety buffer; keep the
  unknown-when-all-unknown and negative-preserved semantics.
- [ ] 2.5 Leave hard-stop gating, reservation-for-probes, reset/reclassify and the
  historical-reserve guard unchanged.

## 3. Verification

- [ ] 3.1 Run targeted tests: `test_quota.py`, `test_live_quota_ingestion.py`,
  `test_quota_normalize.py`, `test_allocation.py`.
- [ ] 3.2 Run `.venv/bin/python -m pytest -q`.
- [ ] 3.3 Run `npx --yes @fission-ai/openspec@latest validate update-quota-manager-binding-capacity --strict`.
- [ ] 3.4 Use Code Simplifier before finishing.
- [ ] 3.5 Update `completion.review` and shrink `tests/spec_coverage_pending.txt`.
