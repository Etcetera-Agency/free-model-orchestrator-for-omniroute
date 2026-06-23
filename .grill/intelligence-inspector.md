# Grill: intelligence-forecast extension to the Hermes Inspector
Date: 2026-06-23

## Intent
Make the Hermes Inspector forecast not just *demand* (calls/tokens) but *how
smart the model for a role needs to be*. The forecast should decide the target
AA quality level for each role so the combo builder picks a model that is neither
too weak (research agent degrades) nor wastefully strong. Fills the long-reserved
`InspectorForecast.model_choice` placeholder.

## Constraints
- Spec rule stays: deterministic code gathers everything and assembles prompts;
  the Inspector never reads Hermes files or diffs state ("Inspector is prompt-only").
- Must reuse the existing band machinery (`forecast.quality_band_for_demand`,
  role `minimum/maximum_quality_metric/value`) — not invent a parallel tier system.
- Reuse the existing AA metric enum `{intelligence_index, coding_index, agentic_index}`.
- Free-model pool only — tiers must reflect what free models actually span.
- Every role must end up with a band, including persona-less ones; none left unmodeled.

## Key decisions
- Decision: Intelligence signal source = a role's task-describing text, aggregated
  over ALL its consumers — NOT only profiles. Reason: cron/webhook/aux also need a
  model. Alternative rejected: per-profile only (left persona-less roles unmodeled).
  - `agent_profile`/`service` → profile `SOUL.md` + `AGENTS.md` + `allowed_tools`.
    (Note: in a Hermes profile dir `AGENTS.md` = agent workspace instructions, per
    upstream NousResearch/hermes-agent — NOT the openspec `AGENTS.md` of this dev repo.)
  - `cron_job` → the job's prompt/description.
  - `auxiliary` → the slot's declared purpose in `config.yaml`.
  - consumer with no describing text → no LLM call, role takes `adequacy_floor`.
- Decision: Output is `(capability_axis, anchor/tier)` + confidence, NOT a raw AA
  number from the LLM. Reason: the model reliably ranks "reasoning-heavy → high" but
  cannot calibrate "needs intelligence_index ≥ 62.4" (false precision). Deterministic
  code maps tier→AA anchor. Alternative rejected: LLM emits raw index.
- Decision: Injection point = Inspector sets `anchor` + `capability_axis` (+ optional
  `adequacy_floor`); `min`/`max` stay derived by `quality_band_for_demand` from
  demand/capacity. Reason: "how smart" (anchor) and "how wide for throughput" (band)
  are separate concerns; the Inspector has no capacity data. Alternative rejected:
  Inspector dictating hard min/max edges.
- Decision: Role anchor = `max` over the role's consumers' assessed needs. Reason:
  a shared combo must serve its most demanding consumer or that one degrades.
- Decision: Separate site `hermes-intelligence-inspector`, advisory. Reason: different
  granularity, cadence (persona changes rarely), prompt budget, independent failure
  (fall back to anchor-from-seed). Alternative rejected: extend aggregate `hermes-inspector`.
- Decision: Assess each describing-text **unit individually** (one call per unit),
  NOT one aggregated per-role prompt. Cache each unit's verdict by content hash;
  aggregate `max` per role then pass into the forecast. Reason: a SOUL+AGENTS unit
  won't fit one prompt with everything else; per-unit caching avoids re-running the
  LLM on unchanged files. Alternative rejected: single per-role prompt.
- Decision: cron job prompt is carried into the inventory (today dropped) so cron
  roles are assessed by task, not floored.
- Decision: raise `max_prompt_chars` for this site (6000 too small for SOUL+AGENTS).
- Decision: MVP fixes 3 tiers (low/medium/high); clustering tiers from the real
  free-model AA distribution is a follow-up; no `frontier` tier among free models.
- Decision: Pre-build a default grid of reusable combos spanning the AA range; roles
  snap to the nearest cell; unique combos only for roles that fit no cell. Reason: the
  band needs a broad pool "to choose from"; maximizes reuse + predictability.
  Grid: `axis {intelligence,coding,agentic} × tier {low,medium,high}` + a cheap
  auxiliary cell.
- Decision: **Every combo is filled from the grid — no hand-maintained combos.** Main
  roles snap by the Inspector's persona anchor; the 13 existing `fmo-*` combos
  reconcile in; **auxiliary combos snap to the cheap auxiliary cell with no Inspector
  call** (narrow/mechanical function — LLM verdict adds nothing). Reason: user wants
  one uniform mechanism, "don't overthink the auxiliaries". Alternative rejected:
  hand-maintaining the 10 aux combos (option C).
- Decision (data-backed, fixtures): no `frontier` tier among free models (ceilings
  intel 59.9 / coding 74.9 / agentic 80.6); tier boundaries are per-axis (the axes'
  ranges differ 2–3×, so a shared absolute cut is wrong). Tiering operates on the
  ~348 registered text/chat models; ~102 non-text endpoints (embed/ASR/TTS/image/
  OCR) are matched by capability, not intelligence tier. See `design.md`.
- Decision: the grid is keyed by the **full requirement profile**
  `(axis, tier, required_capabilities, context_class)`, NOT axis×tier — capability
  and context window are dimensions of the cell, not post-filters (a cell must be a
  real populated combo for the whole profile, e.g. vision + 1M + high-intel). Reason:
  filtering a generic cell could leave it empty. User: "это всё влияет на сетку".
- Decision: grid is **demand-driven** — one combo per profile tuple real roles
  actually exhibit, not the cartesian product (~100+); singleton tuple → unique combo.
- Decision: auxiliary = combo **per capability** (`aux-text/tools/struct/vision`),
  each built from the cheapest models satisfying that capability; aux roles snap there
  with no Inspector call. User: aux differ by tooling, can't share one cheap cell.
- Decision: `minimum_context_window` per role = `max(`static requirement,
  demand-Inspector `average_input_tokens × headroom)`; gate via existing
  `effective_context_window`/`_context_window_eligibility`. Capacity-thin corners:
  vision 52, 1M+ context 58, high-intelligence 38 endpoints → watch band `degraded`.
- Decision: the grid is **bootstrapped once** at initial deploy, never
  re-bootstrapped wholesale. Steady state = continuous rebalance + lazy mint of a
  unique per-agent combo when a new agent's profile tuple is uncovered. User: "сетка
  только в начале сетапится, дальше постоянно ребалансится и могут добавляться новые
  уникальные комбо под агента".
- Decision: **bootstrap is minimal — one seed model per default combo** (sets the
  anchor), NOT a pre-filled ~8-member list. The agent-driven rebalance grows each
  combo from its seed (band widens around the anchor to meet the agents' demand,
  members re-rank). Reuses existing `_seed_quality_bands` (one seed endpoint) +
  `quality_band_for_demand` (widen by demand). User: "бутстрап под дефолтные комбо с
  одной сид моделью, на основе агентов делается их ребаланс".
- Decision: grid cells are **living combos** that ride the existing rebalance
  machinery (priority reorder w/ hysteresis, quota recalibration cron, reactive
  triggers, drift-guarded apply). The grid owns only the *target* (profile tuple +
  anchor); rebalance owns live membership/ordering. The **anchor is stable across
  rebalances** — recomputed only on persona/description-hash change, never on quota
  recalibration/reorder (else churn). Thin-corner shortfall → band `degraded`, never
  silent re-anchor down. User: "эти комбо они ребалансируются".

## Surfaced assumptions
- A Hermes profile dir contains `SOUL.md`/`AGENTS.md` siblings to `config.yaml`
  (upstream layout); FMO already reads that dir via `read_profile_slots`.
- One combo per role (1:1) holds; combos are reused across roles, some roles unique.
- The openclaw portfolio is reference-only; agents there map to Hermes profiles and
  are grouped by `runtime_profile`/dep — not consumed directly.

## Open questions
- Tier count beyond the MVP: when to switch from fixed-3 to clustering the real
  free-model AA distribution (and the cluster method).

## Out of scope
- Using the openclaw portfolio agents directly (reference only).
- Letting the Inspector read Hermes files itself (violates prompt-only rule).
- A parallel tiering system separate from the existing quality-band fields.
