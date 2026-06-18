# Change: Shared Instructor + Pydantic runtime adapter

## Why

The four structured-LLM sites (quota-research inspector, Hermes role Inspector
forecast, smart-combo-reviewer, AA index migration) need one shared Instructor +
Pydantic runtime adapter instead of ad-hoc call sites.

## What Changes

- Add a shared Instructor + Pydantic runtime adapter: provider config,
  OmniRoute/OpenAI-compatible transport, structured-output mode, retries, prompt
  assembly/redaction, and per-site model limits.
- Apply advisory fail-open behavior for smart-combo-reviewer and AA index
  migration (proceed deterministically when the LLM yields nothing usable) and
  deterministic failure handling for all four sites.
- Record representative structured completions (valid and malformed) for the
  validator/repair path tests.

## Impact

- Affected specs: `llm-runtime`
- Affected code (later): `src/fmo/llm_runtime.py`, `src/fmo/quota_research.py`,
  `src/fmo/hermes_inventory.py`, `src/fmo/smart_review.py`,
  `src/fmo/aa_migration.py`
- Spec-only proposal; no implementation in this change.
