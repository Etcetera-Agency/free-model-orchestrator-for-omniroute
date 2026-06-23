# Tasks: Add the Hermes intelligence Inspector

## 1. Per-unit describing-text gathering (deterministic)
- [ ] 1.1 Read `SOUL.md` + `AGENTS.md` siblings of each profile `config.yaml`
- [ ] 1.2 Carry the cron job prompt into the inventory model (`parse_cron_jobs`
  currently drops it); surface `allowed_tools` and aux-slot purpose
- [ ] 1.3 Assemble one prompt per describing unit (not per role); units with no
  text are skipped
- [ ] 1.4 Redact secrets via the existing runtime path; honour `max_prompt_chars`

## 2. Intelligence Inspector site
- [ ] 2.1 Add `hermes-intelligence-inspector` `LlmSiteConfig` (advisory, raised
  `max_prompt_chars` — a SOUL+AGENTS unit exceeds 6000)
- [ ] 2.2 Define `IntelligenceForecastResponse` (`capability_axis`, `tier`, `confidence`)
- [ ] 2.3 `run_intelligence_inspector(call_instructor, prompt)` per unit; advisory
  failure falls back to anchor-from-seed without blocking demand forecast

## 3. Per-unit cache + anchor → band wiring
- [ ] 3.1 Store a content hash per unit; re-assess only changed units, reuse cached
  verdicts otherwise
- [ ] 3.2 Map `tier → anchor` value per axis (deterministic table)
- [ ] 3.3 Role anchor = `max` over its units' cached verdicts; axis from the most
  demanding unit; aggregate then pass into the forecast
- [ ] 3.4 Set role `minimum_quality_metric` = axis and feed `anchor` into
  `quality_band_for_demand`; stop hardcoding `intelligence_index`
- [ ] 3.5 Description-less role → `adequacy_floor`
- [ ] 3.6 Fill `InspectorForecast.model_choice` with `(axis, tier, anchor)`

## 4. Default-combo grid + snap
- [ ] 4.1 Bootstrap reusable combos over `axis × tier` (3 tiers, no frontier) +
  auxiliary set; tier boundaries = per-axis tertiles of the **registered** pool
  (`omniroute_v1_models.json`); `(axis, tier) → anchor` = median of the bucket;
  reconcile with the 13 existing `fmo-*` combos, don't mint a parallel set (design.md)
- [ ] 4.3 Tier only text/chat models; non-text endpoints (~102: embed/ASR/TTS/
  image/OCR/moderation/rerank) are matched by capability, not intelligence tier. The
  small AA-unscored chat tail keeps the existing router/uncertainty path.
- [ ] 4.2 Fill every combo from the grid (no hand-maintained combos): main roles
  snap by Inspector anchor; the 13 `fmo-*` reconcile in, auxiliaries snap to the
  cheap auxiliary cell without an Inspector call; mint a unique combo only when no
  cell fits

## 5. Change-driven refresh
- [ ] 5.1 Extend `inventory_diff` with the per-unit hash store so a role's anchor
  re-aggregates only when one of its units' verdicts changes

## 6. Tests
- [ ] 6.1 Per-unit prompt assembly across `agent_profile`/`cron_job`/`auxiliary`
- [ ] 6.2 `max` anchor aggregation over units + axis selection
- [ ] 6.3 tier→anchor mapping and band injection (min/max still demand-derived)
- [ ] 6.4 Floor fallback for description-less roles
- [ ] 6.5 Unchanged-unit hash hit skips the Inspector call
- [ ] 6.6 Grid snap (main by anchor, aux to cheap cell w/o call) vs unique-combo minting
- [ ] 6.7 Advisory failure → anchor-from-seed fallback, demand forecast intact
- [ ] 6.8 Update `test_role_lifecycle` `model_choice` assertion
