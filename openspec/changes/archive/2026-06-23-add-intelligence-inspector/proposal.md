# Change: Add the Hermes intelligence Inspector (per-role quality anchor)

## Why

The Hermes Inspector forecasts only *demand* — `expected_calls` and average
tokens (`hermes_inventory.run_inspector`). It cannot say *how smart* a role's
model must be: its prompt (`assemble_inspector_prompt`) carries only quantitative
consumer fields (`role_id, consumer_type, consumer, cadence, calls_per_run`) with
no signal about what each agent actually does.

As a result the combo quality target is set blindly: `_seed_quality_bands`
anchors every band on a **seed endpoint** and hardcodes `intelligence_index`
(`composition_stages/roles.py:175`). A reasoning-heavy role and a mechanical
extractor can land on the same anchor. The long-reserved
`InspectorForecast.model_choice` placeholder (asserted `None` in
`test_role_lifecycle.py:96`) was always meant to carry this verdict.

This change adds a second, prompt-only Inspector that reads each role's
task-describing text and emits the **quality anchor** (which AA axis, how high)
that feeds the existing band machinery — so the combo builder picks a model
matched to the role's cognitive load instead of an arbitrary seed.

## What Changes

- Add a new Instructor site `hermes-intelligence-inspector` (advisory), separate
  from the aggregate demand `hermes-inspector`.
- Assess each task-describing text **unit individually** (one Inspector call per
  unit), prompt-only — deterministic code assembles each prompt:
  - `agent_profile`/`service` → profile `SOUL.md` + `AGENTS.md` + `allowed_tools`
    (the Hermes-profile `AGENTS.md`, i.e. agent workspace instructions);
  - `cron_job` → the job's prompt (carried into inventory; today
    `parse_cron_jobs` drops it);
  - `auxiliary` → the slot's declared purpose;
  - consumer with no describing text is not assessed.
- **Cache each unit's verdict by the unit's content hash**: an unchanged file/text
  is never re-sent to the LLM. The role anchor is the `max` over its units' cached
  verdicts — per-unit metrics are aggregated and then passed into the forecast.
- Each Inspector call returns `capability_axis ∈ {intelligence_index, coding_index,
  agentic_index}` + `tier` (ordinal) + `confidence` — not a raw AA value.
  Deterministic code maps `tier → anchor` value and sets the role's
  `minimum_quality_metric` (= axis) and band **anchor**; `min`/`max` stay derived by
  `quality_band_for_demand` from demand/capacity.
- Raise `max_prompt_chars` for this site (a single SOUL+AGENTS unit exceeds the
  6000 demand-Inspector cap); per-unit assessment keeps each prompt bounded.
- A role whose consumers carry no describing text (e.g. a bare webhook) takes the
  global `adequacy_floor` — every role still gets a band, no LLM call wasted.
- Extend `inventory_diff` with a **per-unit content-hash store**: only units whose
  hash changed are re-assessed; a role's anchor is re-aggregated only when one of
  its units' verdicts changed, not on every consumer-set diff.
- Bootstrap a **default grid of reusable combos** over the registered text/chat pool,
  keyed by the full profile `(axis, tier, required_capabilities, context_class)` —
  capability (vision/tool_calling/structured) and context window are **dimensions of
  the cell**, gated as hard filters before the tier orders members (reusing
  `scoring.py` capabilities + `_context_window_eligibility`). The grid is
  **demand-driven** (one combo per profile tuple real roles exhibit, not the cartesian
  product). **Every role is filled from the grid** — main roles snap by Inspector
  anchor; the 13 existing `fmo-*` combos reconcile in; auxiliary roles snap to the
  cheapest combo for their profile with no Inspector call. A unique combo is minted
  only for a tuple seen once. `minimum_context_window` = `max(`static requirement,
  demand-forecast `input_tokens × headroom)`.
- Fill `InspectorForecast.model_choice` with the resolved `(axis, tier, anchor)`.
- Advisory failure path: if the intelligence Inspector is unavailable, fall back
  to the current anchor-from-seed behaviour without blocking the demand forecast.

## Impact

- Affected specs: `hermes-inventory` (new requirements; demand Inspector unchanged).
- Affected code: `src/fmo/hermes_inventory.py` (per-role prompt assembly, new
  `run_intelligence_inspector`, `InspectorForecast.model_choice`),
  `src/fmo/forecast.py` / `src/fmo/composition_stages/roles.py` (anchor + axis from
  Inspector instead of seed/hardcoded metric, default-combo grid + snap),
  `src/fmo/llm_runtime.py` (new site config; likely a larger `max_prompt_chars`).
- New tests: per-role prompt aggregation across consumer types, `max` anchor
  aggregation, tier→anchor mapping, floor fallback for description-less roles,
  description-hash trigger, grid snap vs unique combo, advisory failure fallback.

## Resolved during grilling

- cron prompt is carried into inventory (Task 1.2) so cron roles are assessed.
- Per-unit assessment + per-unit content-hash cache; aggregate `max` into forecast.
- Raise `max_prompt_chars` for this site.

## Tiering (resolved from fixture data — see `design.md`)

Free-model AA distribution (`artificial_analysis_language_models_free.json`,
503 models) confirms **3 tiers, no `frontier`** (intelligence ceiling 59.9, coding
74.9, agentic 80.6 — nothing near 90–100). Tier **boundaries are per-axis**
(tertiles of the confirmed-free pool), not a shared absolute cut, because the axes'
ranges differ 2–3× (`high ≥ 40` is 33 intelligence models but 133 agentic ones).

## Open Questions (resolve before/while implementing)

1. **Full density clustering** (variable tier count per axis) vs the MVP's fixed-3 +
   per-axis tertiles — deferred follow-up; revisit if tertiles prove too coarse.
