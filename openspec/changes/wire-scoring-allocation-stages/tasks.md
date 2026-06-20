# Implementation Tasks

## 1. TDD Coverage

- [ ] 1.1 Add a failing effect test: `role-scoring` persists per-role endpoint
  scores from real scoring inputs.
- [ ] 1.2 Add a failing effect test: `allocation` writes `allocation_plans` rows
  (targets + constraint report), one priority combo per role, with global
  allocation across roles and heavy-role separation.
- [ ] 1.3 Add a failing effect test: the oversubscription gate blocks a
  zero-capacity pool and degraded modes use no paid fallback.
- [ ] 1.4 Add a failing effect test: `diff` computes and persists the minimal
  change against current OmniRoute state without mutating it.
- [ ] 1.5 Add a failing test that swapping any adapter for unconditional success
  fails the harness.
- [ ] 1.6 Bind scenarios with `@pytest.mark.spec(...)` and stage them in
  `tests/spec_coverage_pending.txt` until their tests land.

## 2. Implementation

- [ ] 2.1 Add a `role-scoring` adapter calling `scoring`, persisting scores.
- [ ] 2.2 Add an `allocation` adapter calling `forecast` + `allocation`,
  persisting allocation plans with deterministic stable ordering.
- [ ] 2.3 Add a `diff` adapter calling the `applier` diff path, persisting the
  computed minimal diff read-only against OmniRoute.
- [ ] 2.4 Register the three adapters in the per-stage registry so `full`
  advances to `apply`.

## 3. Verification

- [ ] 3.1 Run targeted tests for scoring, allocation, composition, pipeline.
- [ ] 3.2 Run `.venv/bin/python -m pytest -q`.
- [ ] 3.3 Run `npx --yes @fission-ai/openspec@latest validate --all --strict`.
- [ ] 3.4 Use Code Simplifier before finishing.
- [ ] 3.5 Update `completion.review` and shrink `tests/spec_coverage_pending.txt`.
