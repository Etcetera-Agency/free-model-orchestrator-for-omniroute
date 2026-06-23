# Change: Give smart-combo-reviewer full deterministic context

## Why

`smart-combo-reviewer` currently receives only the ordered deterministic combo
IDs. That makes the advisory LLM mostly blind: it cannot evaluate why endpoints
were selected, whether the diff respects role requirements, whether quota is
thin, whether provider/account diversity is weak, or whether the deterministic
validator already flagged risk.

Other inspector sites already follow a richer pattern: deterministic code
assembles a bounded, redacted prompt from named inputs, loads the site's prompt
file, and lets the shared Instructor runtime validate structured output. The
reviewer should use the same pattern while staying advisory and fail-open.

This change depends on `update-combo-member-identity`: reviewer patches should be
described against the same structured provider/model/account, quota-pool, and
canonical-model identities that deterministic allocation/apply can validate.

## What Changes

- Replace the reviewer input from `{"combo": deterministic_combo}` with a
  redacted all-cells review brief containing:
  - every reviewed combo-grid cell profile and current/target member order;
  - snapped consumers per cell, including role demand, token pressure,
    criticality, purpose summary, and Inspector confidence;
  - current live combo members (`before`);
  - deterministic target combo members (`after`);
  - minimal diff (`add`, `remove`);
  - role requirements and forecast demand;
  - allocation constraint report for the role;
  - candidate endpoint metadata used by scoring/allocation;
  - quota attribution and latest remaining quota summary;
  - provider/account diversity summary;
  - deterministic validation report and apply precondition summary.
- Wire `reference/prompts/smart-combo-reviewer.md` via
  `LlmSiteConfig.prompt_path`, matching quota and Hermes inspectors.
- Keep one advisory structured call per reviewed combo and keep
  `max_prompt_chars` bounded. If context is too large, deterministic code SHALL
  summarize and rank candidates before prompt assembly instead of truncating away
  required sections.
- Preserve the core safety invariant: reviewer output is persisted for operator
  visibility but never changes the applied diff in this slice.
- Add deterministic payload tests so the suite proves the reviewer sees enough
  facts to make a meaningful advisory decision.

## Impact

- Affected specs: `smart-combo-reviewer`.
- Affected code: `src/fmo/smart_review.py`,
  `src/fmo/composition_stages/apply.py`, `reference/prompts/smart-combo-reviewer.md`,
  and tests around composition diff/advisory runtime.
- No change to apply semantics, combo smoke tests, rollback, quota gates, or
  deterministic allocation.
