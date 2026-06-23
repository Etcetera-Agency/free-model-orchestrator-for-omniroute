# Implementation Tasks

## 1. TDD Coverage

- [x] 1.1 Add a failing test proving `smart-combo-reviewer` receives
  `current_combo`, `target_combo`, `deterministic_diff`, and `role_id`.
- [x] 1.2 Add a failing test proving reviewer context includes role
  requirements, demand forecast, allocation constraint report, candidate
  registry, quota summary, diversity summary, validation report, and apply
  precondition summary.
- [x] 1.3 Add a failing test proving the reviewer uses
  `reference/prompts/smart-combo-reviewer.md` through `LlmSiteConfig.prompt_path`.
- [x] 1.4 Add a failing test proving secret-like context values are not present
  in the final prompt.
- [x] 1.5 Add a failing test proving an oversized candidate registry is
  summarized deterministically while required top-level sections remain present.
- [x] 1.6 Keep existing tests proving reviewer success, failure, or disabled
  trigger does not change the applied deterministic diff.
- [x] 1.7 Bind all new scenarios with `@pytest.mark.spec(...)` and update
  `tests/spec_coverage_pending.txt` as coverage lands.

## 2. Implementation

- [x] 2.1 Add a deterministic `build_combo_review_context` helper that gathers
  role, plan, candidate, quota, diversity, validation, and precondition facts.
- [x] 2.2 Change `run_combo_review` to accept the full review context and render
  it via the smart reviewer prompt file.
- [x] 2.3 Update the diff stage to pass the allocation plan and repository facts
  into the context builder before invoking the reviewer.
- [x] 2.4 Update `reference/prompts/smart-combo-reviewer.md` to describe every
  input section and preserve hard rules: advisory only, no invented endpoints,
  no quota/strategy/config changes.
- [x] 2.5 Keep `ComboReviewResponse` and persisted advisory payload stable unless
  tests prove a field is required for operator visibility.
- [x] 2.6 Add or update `AICODE-NOTE:` anchors around the context builder if the
  data-gathering path is non-obvious.

## 3. Verification

- [x] 3.1 Run targeted tests for advisory review and diff stage.
- [x] 3.2 Defer `.venv/bin/python -m pytest -q` to the final all-slice verification pass per operator instruction.
- [x] 3.3 Run OpenSpec validation when the CLI is available:
  `openspec validate update-smart-combo-review-context --strict`.
- [x] 3.4 Use Code Simplifier before finishing implemented slices.
- [x] 3.5 Update `openspec/TODO.md` if implementation or review discovers
  follow-up work.
