# Implementation Tasks

## 1. TDD Coverage

- [x] 1.1 Add a failing test: a snapshot range `[low, high]` with `previous_limit`
  inside the range resolves to `previous_limit` (stable, no churn).
- [x] 1.2 Add a failing test: a range entirely **below** `previous_limit`
  (downgrade) resolves to the range's upper bound `high`.
- [x] 1.3 Add a failing test: a range entirely **above** `previous_limit`
  (unverified upgrade) resolves to the range's lower bound `low`.
- [x] 1.4 Add a failing test: a range with no `previous_limit` resolves to the
  conservative lower bound `low`.
- [x] 1.5 Add a failing test: `previous_limit` is passed through
  `research_quota_rule` → inspector (the inspector call/prompt receives it).
- [x] 1.6 Bind scenarios with `@pytest.mark.spec(...)` and stage them in
  `tests/spec_coverage_pending.txt` until their tests land.
- [x] 1.7 Add failing shared-runtime coverage proving every Inspector site leaves
  `LlmSiteConfig.model` unset and relies on the runtime resolver's concrete
  `provider_model_id`.
- [x] 1.8 Add failing shared-runtime coverage proving any resolver-less Inspector
  call fails closed as `llm_model_unavailable` instead of calling any fabricated
  Inspector combo.
- [x] 1.9 Add failing resolver coverage proving candidate selection performs a
  fresh live quota/liveness check before returning a provider model, skips a
  candidate whose quota is exhausted, locked out, or has `percentRemaining <= 10`,
  and tries the next eligible confirmed-free model.

## 2. Implementation

- [x] 2.1 Add the `{{previous_limit}}` input variable and the range-resolution
  rule (clamp the prior limit into `[low, high]`; conservative `low` when no prior
  limit) to the prompt file `reference/prompts/quota-research.md`.
- [x] 2.2 Wire the prompt file in `run_quota_inspector` (set `prompt_path` on the
  `LlmSiteConfig`) and thread `previous_limit` through `_extract_claims` →
  `run_quota_inspector` into the inspector `context` so `{{previous_limit}}`
  resolves; keep the snapshot text available to the template.
- [x] 2.3 Reword `build_quota_query` to request the cumulative budget axes in
  canonical units, the hard-stop distinction, and broad (community + official)
  sources, keeping it natural-language and date-aware.
- [x] 2.4 Keep the deterministic fallback, `summary_confidence_cap`, and
  worsen-quota safe-mode unchanged; resolution stays within evidence bounds and
  under the cap.
- [x] 2.5 Make `LlmSiteConfig.model` optional and update every Inspector site to
  leave it unset. The runtime resolver (`select_llm_model`) SHALL provide the
  concrete `provider_model_id` at call time; no Inspector SHALL hardcode a
  fabricated combo.
- [x] 2.6 Update the Instructor runtime adapter so an unset site model requires a
  resolver-selected concrete provider model and fails closed as
  `llm_model_unavailable` when none is available.
- [x] 2.7 Update `select_llm_model`/runtime model resolution so each candidate is
  checked against live quota/liveness at selection time. A candidate with
  `percentRemaining <= 10`, `resetAt` in the future, exhausted
  `quotaTotal`/`quotaUsed`, or unavailable live quota evidence SHALL be skipped
  before returning a `provider_model_id`.

## 3. Verification

- [x] 3.1 Run targeted tests: `test_quota.py`, `test_quota_research_ingestion.py`,
  `test_instructor_runtime_adapter.py`.
- [x] 3.2 Run `.venv/bin/python -m pytest -q`.
- [x] 3.3 Run `openspec validate update-quota-research-range-resolution --strict`.
- [x] 3.4 Use Code Simplifier before finishing.
- [x] 3.5 Update `tests/spec_coverage_pending.txt` and `openspec/TODO.md`.
- [x] 3.6 Run targeted shared-runtime/Inspector tests after 1.7, 1.8, 2.5, and
  2.6 land.
- [x] 3.7 Run `.venv/bin/python -m pytest -q` after shared Inspector model
  resolution lands.
- [x] 3.8 Use Code Simplifier before finishing the shared Inspector model
  resolution slice and update `completion.review` if any fixes are needed.
