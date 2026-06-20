# Change: Wire the production Instructor + Pydantic runtime

## Why

`project.md` declares exactly four Instructor/Pydantic structured-LLM sites as
part of the project. The runtime (`src/fmo/llm_runtime.py`) and every site
(`quota_research.run_quota_inspector`, `smart_review.run_combo_review`,
`hermes_inventory.run_inspector`, `aa_migration.run_migration_agent`) are
implemented and unit tested, but **no production code constructs
`SharedInstructorRuntime` / `LlmProviderConfig` with a real transport**. As a
result:

- the production `quota-research` stage uses the deterministic regex fallback
  (`extract_summary_claim`) and never calls the quota inspector;
- the advisory `smart-combo-reviewer` is never invoked during a `full` run.

Today there is no real `instructor` dependency at all: `instructor` is not in
`pyproject.toml`, is not installed, and is imported nowhere. `llm_runtime.py` is
a hand-rolled wrapper around an injected `transport` callable, only ever fed a
fake in tests. This diverges from `project.md`, which mandates "Instructor +
Pydantic".

This slice adopts the real `instructor` library: it adds `instructor` as a
dependency and builds the shared production client with
`instructor.from_openai(...)` pointed at the OmniRoute OpenAI-compatible `/v1`
surface, then routes the first two sites through it. The remaining two sites are
wired by their own slices (`wire-aa-index-cli-dispatch`,
`wire-hermes-inventory-source`) reusing this client.

This is a correction toward `project.md`, not a doc change: structured output is
produced by Instructor + Pydantic response models, deterministic code remains the
source of truth, and advisory sites stay fail-open.

## What Changes

- Add `instructor` (and its OpenAI client backing) as a runtime dependency in
  `pyproject.toml`.
- Build the production client with `instructor.from_openai`, wired to a
  `SharedInstructorRuntime` from validated startup config: base URL derived from
  `OMNIROUTE_URL` (`/v1`) and api key. The runtime's transport delegates to
  Instructor's `response_model`-typed structured completion. Add the LLM
  provider/site config keys to environment validation.
- Implement the **LLM model selection/substitution procedure** (per
  `reference/docs/modules/15-llm-usage.md`): there is **no dedicated combo for the
  orchestrator** — a single confirmed-free model is selected by criteria and
  substituted as the call's model. Criterion (per modules 13/20): the
  **confirmed-free model with the maximum AA `intelligence_index`**, healthy
  endpoint with remaining quota, falling to the next model by descending
  `intelligence_index` on unavailability. Resolution order: (1) that
  highest-index confirmed-free catalog model; (2) a manually configured
  **bootstrap model id** that MUST be confirmed free; (3) **degrade to no-LLM
  mode** — never fall back to a paid or unconfirmed model. This preserves the
  core invariant for LLM calls themselves.
- Route the `quota-research` stage through `run_quota_inspector` for claim
  extraction, keeping `extract_summary_claim` as the deterministic fallback when
  the inspector is unavailable or returns an unusable claim (fail-open, capped
  confidence unchanged).
- Invoke `smart_review.run_combo_review` as an advisory pass over the computed
  combo diff; its output is recorded but never blocks or mutates the
  deterministic plan.
- Add executable effect tests proving the Instructor client is constructed via
  `instructor.from_openai`, the inspector path is taken when available, the
  deterministic fallback runs when it is not, and the advisory reviewer cannot
  change the applied diff. Tests stub only the network boundary (the OpenAI
  client transport) — never a live model.

## Impact

- Affected specs: `llm-runtime`, `quota-research`, `smart-combo-reviewer`.
- Affected code: `pyproject.toml` (new `instructor` dependency),
  `src/fmo/composition.py`, `src/fmo/bootstrap.py`, `src/fmo/config.py`,
  `src/fmo/llm_runtime.py`, `src/fmo/quota_research.py`,
  `src/fmo/smart_review.py`, `tests/`.
- New external contract: structured chat calls to OmniRoute `/v1/chat/completions`
  for the two wired sites, with a confirmed-free model selected and substituted
  per call. No change to deterministic capacity or apply logic.
- Depends on: `wire-scoring-allocation-stages` (diff stage exists). Model
  selection reuses the confirmed-free catalog the pipeline already produces; until
  a model qualifies, the bootstrap model or no-LLM mode applies.
