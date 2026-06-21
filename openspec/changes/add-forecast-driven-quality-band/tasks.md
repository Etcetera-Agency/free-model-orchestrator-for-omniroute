# Implementation Tasks (TDD)

Write each test first (red) → green → refactor. PostgreSQL is real (schema +
migration). AA metrics from recorded real Artificial Analysis shapes.

## Schema / migration

- Add `roles.maximum_quality_metric text`, `roles.maximum_quality_value numeric`
  with a check mirroring the existing `minimum_quality_metric` constraint, in
  `reference/db/schema.sql` and a new `reference/db/migrations/` file.

## Tasks

- [ ] 1. TEST: migration adds the `maximum_quality_*` columns and a fresh schema
  install has them → write schema + migration.
- [ ] 2. TEST: a combo holding **exactly one** model anchors the band from that
  model's canonical AA metric and persists `roles.min/max`; a combo with >1
  member keeps the persisted band (no re-derivation) → implement seed-anchored
  set-once writer.
- [ ] 3. TEST: re-seeding (combo stripped back to one model) re-anchors the band
  → implement the single-member re-anchor path.
- [ ] 4. TEST: the band widens until in-band confirmed-free capacity covers
  `protected_requests`, bounded by the adequacy floor → implement the
  forecast-driven band-width helper in `forecast.py`.
- [ ] 5. TEST: a paid seed sets the anchor but is excluded from members → assert
  paid endpoint never enters the combo.
- [ ] 6. TEST: `evaluate_quality_gate` excludes an endpoint **above** the band
  (`above_band`) while still excluding below `min` → add the upper bound; NULL
  `max` preserves min-only behavior.
- [ ] 7. TEST: `build_priority_combo` orders weakest-eligible first and smartest
  last; tie-break by latency among equal quality → invert the sort key.
- [ ] 8. TEST (integration): rebalancing an existing combo with a seed yields an
  in-band, ascending-ordered, demand-sized member list applied via the
  rebalance-only path → wire scoring/allocation to the band.
- [ ] 9. Bind tests with `@pytest.mark.spec("...")`, drop matching lines from
  `tests/spec_coverage_pending.txt`, run full `pytest` and
  `openspec validate add-forecast-driven-quality-band --strict`.
