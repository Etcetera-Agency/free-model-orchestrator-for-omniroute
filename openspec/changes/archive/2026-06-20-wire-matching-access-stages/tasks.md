# Implementation Tasks

## 1. TDD Coverage

- [x] 1.1 Add a failing effect test: `model-matching` writes matched
  provider-endpoint rows for free candidates and stops on no match.
- [x] 1.2 Add a failing effect test: `quota-research` persists quota snapshots
  and rules, capping summary-sourced rules by `summary_confidence_cap`.
- [x] 1.3 Add a failing effect test: `access-classification` writes the
  `confirmed | inferred | assumed_shared | unknown` status with evidence, and
  unknown never becomes free.
- [x] 1.4 Add a failing test that swapping any of the three adapters for
  unconditional success fails the harness.
- [x] 1.5 Bind scenarios with `@pytest.mark.spec(...)` and stage them in
  `tests/spec_coverage_pending.txt` until their tests land.

## 2. Implementation

- [x] 2.1 Add a `model-matching` adapter calling `matcher` and persisting matches.
- [x] 2.2 Add a `quota-research` adapter calling `quota_research`, storing
  content-hashed snapshots and capped rules.
- [x] 2.3 Add an `access-classification` adapter calling `access` +
  `quota_attribution`, persisting status and evidence.
- [x] 2.4 Register the three adapters in the per-stage registry from slice 1 so
  `full` advances past them.
- [x] 2.5 Map external/partial failures to `external_dependency_failed` /
  `partial_stale` exit codes.

## 3. Verification

- [x] 3.1 Run targeted tests for matcher, quota-research, access, composition.
- [x] 3.2 Run `.venv/bin/python -m pytest -q`.
- [x] 3.3 Run `npx --yes @fission-ai/openspec@latest validate --all --strict`.
- [x] 3.4 Use Code Simplifier before finishing.
- [x] 3.5 Update `completion.review` and shrink `tests/spec_coverage_pending.txt`.
