# Implementation Tasks

## 1. TDD Coverage

- [x] 1.1 Add a failing test: `to_requests_per_day` passes `requests/day` through,
  normalizes `requests/month` by `/30`, converts `tokens/day` and `tokens/month`
  by the factor, and returns `None` for `minute`/`hour` windows. *(landed in
  `tests/test_quota_normalize.py`)*
- [x] 1.2 Add a failing test: `binding_capacity` returns the tightest converted
  axis, ignores sub-day rate gates, and returns `None` when no budget axis exists.
  *(landed)*
- [x] 1.3 Add a failing test: `to_requests_per_day` rejects an invalid metric and a
  non-positive factor. *(landed)*
- [x] 1.4 Add a failing test: `tokens_per_request` defaults to 2000 and config
  validation rejects a non-positive value. *(landed / config)*
- [x] 1.5 Add a failing test: telemetry parses token counts per provider/model from
  `/api/usage/analytics`; when the field is absent the token input is left unknown
  (not fabricated).

## 2. Implementation

- [x] 2.1 `quota_normalize.to_requests_per_day` + `binding_capacity`
  + `DEFAULT_TOKENS_PER_REQUEST`. *(landed)*
- [x] 2.2 `config.tokens_per_request` setting (default 2000) + `> 0` validation.
  *(landed)*
- [x] 2.3 Add `tokens` to `TelemetryMetric` and parse a token-count field from the
  `byProvider`/`byModel` analytics items, leaving it unknown when absent.

## 3. Verification

- [x] 3.1 Run targeted tests: `test_quota_normalize.py`, `test_foundation.py`,
  `test_telemetry_ingestion.py`.
- [x] 3.2 Run `.venv/bin/python -m pytest -q`. (Skipped by user request: no full test after each slice.)
- [x] 3.3 Run `npx --yes @fission-ai/openspec@latest validate add-quota-unit-normalization --strict`.
- [x] 3.4 Use Code Simplifier before finishing.
- [x] 3.5 Update `completion.review` and shrink `tests/spec_coverage_pending.txt`.
