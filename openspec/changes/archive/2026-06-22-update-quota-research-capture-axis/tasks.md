# Implementation Tasks

## 1. TDD Coverage

- [x] 1.1 Add a failing test: a summary stating `N tokens per month` yields a
  claim with `metric="tokens"`, the right amount and window — not a `requests`
  claim and not a `missing_amount` error.
- [x] 1.2 Add a failing test: a summary stating `N requests per day` still yields
  `metric="requests"` (no regression).
- [x] 1.3 Add a failing test: a summary stating both a request/day and a
  token/month limit captures both axes.
- [x] 1.4 Add a failing test: a summary expressing only `N requests per minute`
  (or per hour) does NOT activate a capacity rule — the endpoint stays without a
  confirmed budget rule.
- [x] 1.5 Add a failing test: an Instructor inspector claim with `metric="tokens"`
  is carried through unchanged; an inspector claim with a sub-day request window is
  not activated as capacity.
- [x] 1.6 Bind scenarios with `@pytest.mark.spec(...)` and stage them in
  `tests/spec_coverage_pending.txt` until their tests land.

## 2. Implementation

- [x] 2.1 Replace the hardcoded `metric="requests"` in `extract_summary_claim`
  with axis detection over the summary text.
- [x] 2.2 Extend `_extract_amount`/`_extract_window` to recognise token phrasing
  (`tokens per day/month`) alongside request phrasing; capture both axes when both
  are present.
- [x] 2.3 Route sub-day request windows out: a `requests` claim with window
  `minute`/`hour` SHALL NOT become a capacity rule (reactive, left to OmniRoute).
- [x] 2.4 Apply the same sub-day-request routing to inspector-returned claims;
  otherwise carry the inspector `metric` through unchanged.
- [x] 2.5 Keep `summary_confidence_cap`, worsen-quota safe-mode and the
  deterministic validator unchanged.

## 3. Verification

- [x] 3.1 Run targeted tests: `test_quota.py`, `test_quota_research_ingestion.py`,
  `test_quota_normalize.py`.
- [x] 3.2 Run `.venv/bin/python -m pytest -q`. (Skipped by user request: no full test after each slice.)
- [x] 3.3 Run `npx --yes @fission-ai/openspec@latest validate update-quota-research-capture-axis --strict`.
- [x] 3.4 Use Code Simplifier before finishing.
- [x] 3.5 Update `completion.review` and shrink `tests/spec_coverage_pending.txt`.
