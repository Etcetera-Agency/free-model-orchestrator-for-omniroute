# Change: Inspector resolves a reported quota range using the prior limit

## Why

A grounded-search snapshot frequently states a quota as a **range** rather than a
single number — "between 200 and 1,000 requests per day", "1M–2M tokens/month" —
because sources disagree or the provider publishes a tier band. But the extracted
claim is a single `amount` (`QuotaClaimResponse.amount`,
[src/fmo/quota_research.py](../../../src/fmo/quota_research.py)), so the range must
be collapsed to one value.

The signal that disambiguates a range is the **previous limit** we already
trusted for this endpoint. Today `previous_limit` is plumbed into
`research_quota_rule` but only reaches `activate_summary_rule` (where it sets the
`safe_mode` flag) — it never reaches the inspector via `_extract_claims` /
`run_quota_inspector` / `_quota_inspector_prompt`. So when the snapshot reports a
range, the inspector has no anchor and picks arbitrarily.

Downgrades are common and legitimate (providers quietly cut free tiers), so the
resolution must adopt a genuinely lower range rather than cling to the old value,
while not churning the limit when the new range still contains it.

## What Changes

- `previous_limit` SHALL be threaded into the inspector path:
  `research_quota_rule` → `_extract_claims` → `run_quota_inspector` →
  `_quota_inspector_prompt`, so the inspector receives the last trusted limit.
- The inspector prompt — which lives in the configured prompt file
  `reference/prompts/quota-research.md` (loaded via
  `llm.sites.quota_research.prompt_file` → `LlmSiteConfig.prompt_path` →
  `assemble_prompt`), not hardcoded in `_quota_inspector_prompt` — SHALL gain a
  `{{previous_limit}}` input variable and a range-resolution rule: when the text
  reports a range `[low, high]`, return a single `amount` inside that range,
  anchored to the prior limit — the value in `[low, high]` closest to
  `previous_limit` (clamp the prior limit into the range). When `previous_limit`
  is unknown, choose the conservative lower bound `low`.
- `previous_limit` SHALL be passed into the inspector `context` so the template's
  `{{previous_limit}}` placeholder resolves. (Today `run_quota_inspector` builds
  `LlmSiteConfig` without `prompt_path` and passes a hand-concatenated
  `context={"prompt": ...}`, so the reference prompt file is not actually wired;
  this slice wires the prompt file and threads the new variable through.)
- Fabricated Inspector combo routes SHALL be removed from every Inspector site.
  These combos are not real provider models. All Inspectors SHALL use one shared
  approach: run on a **concrete provider model** chosen at call time by the
  runtime `model_resolver`.
  In production that resolver is `select_llm_model`: it selects the active
  confirmed-free model with remaining quota and healthy status, ordered by
  `intelligence_index DESC`, and returns that model's `provider_model_id`.
  Before returning a candidate, the resolver SHALL perform a fresh live
  quota/liveness check for that candidate so a model whose quota has just been
  consumed is skipped immediately instead of being handed to the Inspector.
  `LlmSiteConfig.model` SHALL become optional and the inspectors SHALL leave it
  unset, so the resolved concrete `provider_model_id` is the only model id. If no
  resolver-selected provider model is available, the adapter SHALL fail closed as
  `llm_model_unavailable`; it SHALL NOT fall back to a hardcoded OmniRoute combo.
- This makes resolution stable (no change when the new range still contains the
  prior limit), conservative on unverified upgrades (a range entirely above the
  prior limit resolves to its lower bound), and faithful on downgrades (a range
  entirely below the prior limit resolves to its upper bound, the least-aggressive
  cut still consistent with the evidence).
- The deterministic validator, `summary_confidence_cap`, and the worsen-quota
  safe-mode rule remain the source of truth; range resolution only chooses a value
  within evidence bounds and never raises a claim above what the gate allows.
- `build_quota_query` SHALL be reworded so the snapshot already carries the values
  the inspector needs — the cumulative budget axes in canonical units, the
  hard-stop distinction, and broad (community + official) sources. Concretely:

  ```text
  What is the free-tier usage quota for {provider} model {model_id}, current as of
  {today}? Give the CUMULATIVE daily and monthly limits, both in requests and in
  tokens: requests per day, requests per month, tokens per day, tokens per month.
  Ignore per-minute/per-second rate limits (RPM/TPM). State whether hitting the
  quota is a hard stop (requests blocked) or a soft throttle. Search broadly: not
  only official documentation but also community sources — developer forums,
  Reddit, GitHub issues, Discord and Stack Overflow — since real observed limits
  often differ from the documented ones. Prefer the official documentation URL as
  evidence, but include community source URLs when they report current real-world
  limits.
  ```

  The query stays natural-language and date-aware; `/v1/search` parameters are
  unchanged.

## Impact

- Affected specs: `llm-runtime`, `quota-research`, `hermes-inventory`.
- Affected code: `src/fmo/quota_research.py` (`_extract_claims`,
  `run_quota_inspector`, `_quota_inspector_prompt`, `build_quota_query`, and the
  `research_quota_rule` call site), the prompt file
  `reference/prompts/quota-research.md`, `tests/`.
- No change to the search query, `/v1/search` parameters, or snapshot
  persistence. The deterministic regex fallback (`extract_summary_claims`) is
  unaffected; it already takes single values, not ranges.
- `previous_limit` keeps its existing `safe_mode` role in `activate_summary_rule`
  unchanged; this change adds a second, additive consumer.
