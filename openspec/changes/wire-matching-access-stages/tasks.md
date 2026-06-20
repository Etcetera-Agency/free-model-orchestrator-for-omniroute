# Implementation Tasks

## 1. TDD Coverage

- [ ] 1.1 Add a failing effect test: `model-matching` writes matched
  provider-endpoint rows for free candidates and stops on no match.
- [ ] 1.2 Add a failing effect test: `quota-research` persists quota snapshots
  and rules, capping summary-sourced rules by `summary_confidence_cap`.
- [ ] 1.3 Add a failing effect test: `access-classification` writes the
  `confirmed | inferred | assumed_shared | unknown` status with evidence, and
  unknown never becomes free.
- [ ] 1.4 Add a failing test that swapping any of the three adapters for
  unconditional success fails the harness.
- [ ] 1.5 Bind scenarios with `@pytest.mark.spec(...)` and stage them in
  `tests/spec_coverage_pending.txt` until their tests land.

## 2. Implementation

- [ ] 2.1 Add a `model-matching` adapter calling `matcher` and persisting matches.
- [ ] 2.2 Add a `quota-research` adapter calling `quota_research`, storing
  content-hashed snapshots and capped rules.
- [ ] 2.3 Add an `access-classification` adapter calling `access` +
  `quota_attribution`, persisting status and evidence.
- [ ] 2.4 Register the three adapters in the per-stage registry from slice 1 so
  `full` advances past them.
- [ ] 2.5 Map external/partial failures to `external_dependency_failed` /
  `partial_stale` exit codes.

## 3. Verification

- [ ] 3.1 Run targeted tests for matcher, quota-research, access, composition.
- [ ] 3.2 Run `.venv/bin/python -m pytest -q`.
- [ ] 3.3 Run `npx --yes @fission-ai/openspec@latest validate --all --strict`.
- [ ] 3.4 Use Code Simplifier before finishing.
- [ ] 3.5 Update `completion.review` and shrink `tests/spec_coverage_pending.txt`.
