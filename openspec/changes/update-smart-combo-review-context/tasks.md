# Implementation Tasks

## 1. TDD Coverage

- [ ] 1.1 Add a failing test proving `smart-combo-reviewer` receives
  `current_combo`, `target_combo`, `deterministic_diff`, and `role_id`.
- [ ] 1.2 Add a failing test proving reviewer context includes role
  requirements, demand forecast, allocation constraint report, candidate
  registry, quota summary, diversity summary, validation report, and apply
  precondition summary.
- [ ] 1.3 Add a failing test proving the reviewer uses
  `reference/prompts/smart-combo-reviewer.md` through `LlmSiteConfig.prompt_path`.
- [ ] 1.4 Add a failing test proving secret-like context values are not present
  in the final prompt.
- [ ] 1.5 Add a failing test proving an oversized candidate registry is
  summarized deterministically while required top-level sections remain present.
- [ ] 1.6 Keep existing tests proving reviewer success, failure, or disabled
  trigger does not change the applied deterministic diff.
- [ ] 1.7 Bind all new scenarios with `@pytest.mark.spec(...)` and update
  `tests/spec_coverage_pending.txt` as coverage lands.

## 2. Implementation

- [ ] 2.1 Add a deterministic `build_combo_review_context` helper that gathers
  role, plan, candidate, quota, diversity, validation, and precondition facts.
- [ ] 2.2 Change `run_combo_review` to accept the full review context and render
  it via the smart reviewer prompt file.
- [ ] 2.3 Update the diff stage to pass the allocation plan and repository facts
  into the context builder before invoking the reviewer.
- [ ] 2.4 Update `reference/prompts/smart-combo-reviewer.md` to describe every
  input section and preserve hard rules: advisory only, no invented endpoints,
  no quota/strategy/config changes.
- [ ] 2.5 Keep `ComboReviewResponse` and persisted advisory payload stable unless
  tests prove a field is required for operator visibility.
- [ ] 2.6 Add or update `AICODE-NOTE:` anchors around the context builder if the
  data-gathering path is non-obvious.

## 3. Verification

- [ ] 3.1 Run targeted tests for advisory review and diff stage.
- [ ] 3.2 Run `.venv/bin/python -m pytest -q`.
- [ ] 3.3 Run OpenSpec validation when the CLI is available:
  `openspec validate update-smart-combo-review-context --strict`.
- [ ] 3.4 Use Code Simplifier before finishing implemented slices.
- [ ] 3.5 Update `openspec/TODO.md` if implementation or review discovers
  follow-up work.
