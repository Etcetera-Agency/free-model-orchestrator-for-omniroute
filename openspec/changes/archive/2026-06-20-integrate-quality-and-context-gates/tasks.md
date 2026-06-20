# Implementation Tasks (TDD)

Write each test first (red) → green → refactor. PostgreSQL is **real**; exercise
the scoring stage end to end through the repository, not the pure functions in
isolation. AA index metrics use recorded real `/api/v2/language/models` shapes.

## Tasks

- [x] 1. TEST (integration): the production `role-scoring` stage excludes an
  endpoint whose effective context (min of known sources) is below the role
  minimum, before weighted scoring → call `effective_context_window` +
  `context_eligible` in the scoring path.
- [x] 2. TEST (integration): unknown context is excluded unless the role sets the
  manual override → wire the override flag through.
- [x] 3. TEST (integration): the production scoring stage applies the role's
  single quality gate as a hard pre-filter and excludes below-gate endpoints →
  call `evaluate_quality_gate` in the scoring path.
- [x] 4. TEST (integration): a missing gate metric yields `unverifiable` and the
  endpoint is excluded unless `allow_unverified_quality_gate` → wire unverifiable
  handling.
- [x] 5. TEST (integration): on an AA index-version mismatch the gate is
  `needs_recalibration`, no new plan is applied, and the current combo is kept →
  wire index-version binding into the stage outcome.
- [x] 6. TEST: `explain-endpoint` reports a context/quality exclusion with its
  real cause → persist the rejection reason / gate status.
- [x] 7. Bind tests with
  `@pytest.mark.spec("context-window-eligibility::...")` and
  `@pytest.mark.spec("quality-gate::...")` and the new role-scorer scenarios,
  drop matching lines from `tests/spec_coverage_pending.txt`, run full `pytest`
  and `openspec validate integrate-quality-and-context-gates --strict`.
