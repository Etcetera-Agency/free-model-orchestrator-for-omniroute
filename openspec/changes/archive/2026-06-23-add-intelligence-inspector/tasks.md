# Tasks: Add the Hermes intelligence Inspector

## 1. Per-unit describing-text gathering (deterministic)
- [x] 1.1 Read `SOUL.md` + `AGENTS.md` siblings of each profile `config.yaml`
- [x] 1.2 Carry the cron job prompt into the inventory model (`parse_cron_jobs`
  currently drops it); surface `allowed_tools` and aux-slot purpose
- [x] 1.3 Assemble one prompt per describing unit (not per role); units with no
  text are skipped
- [x] 1.4 Redact secrets via the existing runtime path; honour `max_prompt_chars`

## 2. Intelligence Inspector site
- [x] 2.1 Add `hermes-intelligence-inspector` `LlmSiteConfig` (advisory, raised
  `max_prompt_chars` — a SOUL+AGENTS unit exceeds 6000)
- [x] 2.2 Define `IntelligenceForecastResponse` (`capability_axis`, `tier`, `confidence`)
- [x] 2.3 `run_intelligence_inspector(call_instructor, prompt)` per unit; advisory
  failure falls back to anchor-from-seed without blocking demand forecast

## 3. Per-unit cache + anchor → band wiring
- [x] 3.1 Store a content hash per unit; re-assess only changed units, reuse cached
  verdicts otherwise
- [x] 3.2 Map `tier → anchor` value per axis (deterministic table)
- [x] 3.3 Role anchor = `max` over its units' cached verdicts; axis from the most
  demanding unit; aggregate then pass into the forecast
- [x] 3.4 Set role `minimum_quality_metric` = axis and feed `anchor` into
  `quality_band_for_demand`; stop hardcoding `intelligence_index`
- [x] 3.5 Description-less role → `adequacy_floor`
- [x] 3.6 Fill `InspectorForecast.model_choice` with `(axis, tier, anchor)`

## 4. Default-combo grid + snap
- [x] 4.1 Bootstrap reusable combos keyed by profile tuple
  `(axis, tier, required_capabilities, context_class)`, demand-driven (one combo per
  tuple real roles exhibit, not cartesian). Tier boundaries = per-axis tertiles of the
  **registered** pool; `(axis, tier) → anchor` = median of the bucket; reconcile with
  the 13 existing `fmo-*` combos, don't mint a parallel set (design.md)
- [x] 4.1b Context window: gate members on `effective_context_window ≥ minimum`
  (reuse `_context_window_eligibility`); `minimum_context_window` =
  `max(`static requirement, demand-forecast `input_tokens × headroom)`
- [x] 4.3 Tier only text/chat models; non-text endpoints (~102: embed/ASR/TTS/
image/OCR/moderation/rerank) are matched by capability, not intelligence tier. The
small AA-unscored chat tail keeps the existing router/uncertainty path.
- [x] 4.2 Capability hard-filter (`issubset`) before tier on every cell; build the
auxiliary family per capability (`aux-text`/`aux-tools`/`aux-struct`/`aux-vision`),
each a combo of the cheapest capability-matching models
- [x] 4.3b Fill every role from the grid (no hand-maintained combos): main roles snap
by Inspector anchor; 13 `fmo-*` reconcile in; aux roles snap to the matching aux
combo without an Inspector call; mint a unique combo only when no cell fits
- [x] 4.4 Server-side combo creation is a SEPARATE task — the concrete bootstrap list
  (13 combos: 9 axis×tier + 4 aux, single-seed each) is in
  `docs/combo-grid-bootstrap.md`; regenerate seeds with the matcher before creating

## 5. Change-driven refresh + rebalance compatibility
- [x] 5.1 Extend `inventory_diff` with the per-unit hash store so a role's anchor
  re-aggregates only when one of its units' verdicts changes
- [x] 5.2 Keep the anchor stable across rebalances: recompute only on persona/
  description-hash change, never on quota recalibration or priority reorder
- [x] 5.3 Grid cells ride existing reorder/recalibration/drift-guarded apply; bootstrap
  sets only initial membership. Thin-corner shortfall (high-intel/1M/vision) sets the
  band `degraded` flag, never silently re-anchors down
- [x] 5.4 Bootstrap is one-time and minimal: one seed model per default combo (sets
  the anchor), NOT a pre-filled list. No wholesale re-bootstrap. Steady state =
  agent-driven rebalance (band widens around seed anchor, members re-rank) + lazy mint
  of a unique per-agent combo (single-seed, then rebalanced) when a tuple is uncovered

## 6. Tests
- [x] 6.1 Per-unit prompt assembly across `agent_profile`/`cron_job`/`auxiliary`
- [x] 6.2 `max` anchor aggregation over units + axis selection
- [x] 6.3 tier→anchor mapping and band injection (min/max still demand-derived)
- [x] 6.4 Floor fallback for description-less roles
- [x] 6.5 Unchanged-unit hash hit skips the Inspector call
- [x] 6.6 Grid snap (main by anchor, aux to cheap cell w/o call) vs unique-combo minting
- [x] 6.7 Advisory failure → anchor-from-seed fallback, demand forecast intact
- [x] 6.8 Update `test_role_lifecycle` `model_choice` assertion
