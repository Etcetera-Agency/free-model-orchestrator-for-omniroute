# add-forecast-driven-quality-band

## Why

A combo must hold models of one **tier band**, with the smartest tried last so
scarce high-quality free quota is preserved as a fallback. Two gaps block this:

1. **No tier is ever enforced.** Roles have `minimum_quality_metric` /
   `minimum_quality_value` (`reference/db/schema.sql`) and the quality gate reads
   them (`_quality_gate_eligibility`, `src/fmo/composition_stages.py`), but
   **nothing writes them** — there is no writer anywhere in `src/`. With the
   columns NULL, `_quality_gate_eligibility` returns `eligible=True` for
   everything, so scoring just ranks whatever free endpoints exist with no tier.

2. **Ordering puts the smartest first.** `build_priority_combo`
   (`src/fmo/allocation.py`) sorts by score **descending** (`reverse=True`), and
   that order is the OmniRoute priority list. Since score is AA-quality dominated,
   the primary (position 0) is the smartest model, so normal traffic burns the
   scarce smart free quota first.

The operator's model: create a combo by hand, seed it with **one** model, run the
script to rebalance. The seed is the **tier anchor** (its AA characteristics),
not a ceiling — the band is computed by the forecast around it, so the seed can
sit anywhere inside the band (models both weaker and smarter than the seed may
join). A paid seed is used only as the AA reference and never becomes a routable
member (the core no-paid invariant).

This slice makes the band real and demand-driven, and flips the ordering so the
smartest land last.

## What Changes

- Add `roles.maximum_quality_value` (and metric) beside `minimum_quality_value`,
  forming a band `[min, max]`.
- Write the band from the **seed anchor**, set-once: when a combo holds exactly
  one model, derive that model's canonical AA metric as the anchor and persist
  the band; when it already holds more than one, keep the persisted band (no
  drift). Re-seeding (operator strips the combo back to one model) re-anchors.
- Compute the band **from the forecast**: the band widens around the seed anchor
  until the confirmed-free capacity of in-band endpoints covers the role's
  `protected_requests`, bounded by an adequacy floor below the anchor. A paid
  seed contributes its AA metric as anchor only; it is excluded from members.
- Enforce the band in the quality gate as a hard pre-filter: `min ≤ AA ≤ max`.
- Order each combo by AA **ascending** (weakest-eligible first, smartest last) so
  the smart tier is the final fallback; keep per-pool caps and stability.

## Impact

- Modified specs: `quality-gate` (band, upper bound, seed-anchored set-once),
  `data-model` (new role column), `allocator` (ascending fallback order),
  `demand-forecast` (band widens to cover protected demand).
- Affected code: `reference/db/schema.sql` + `reference/db/migrations/`,
  `src/fmo/quality.py` (`evaluate_quality_gate` upper bound),
  `src/fmo/composition_stages.py` (`_quality_gate_eligibility`, seed-anchored
  band writer, band/forecast wiring in scoring + allocation),
  `src/fmo/allocation.py` (`build_priority_combo` ordering), `src/fmo/forecast.py`
  (band-width-by-demand helper), `src/fmo/persistence.py` (roles writer).
- Depends on: `add-auxiliary-slot-consumers` (per-combo demand),
  `update-combo-applier-to-rebalance-only` (rebalance-only existing combos).
- Feeds: `add-profile-combo-normalization` (canonical-model anchor lookup).
