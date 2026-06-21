# OpenSpec TODO

No deferred review follow-up work discovered.

## Active proposal slices (pending TDD implementation)

Each slice carries uncovered scenarios listed in
`tests/spec_coverage_pending.txt`. Bind a test, drop the matching line, then
archive when implemented.

Hermes per-profile + auxiliary model slots → combos (proposed, remaining in
requested implementation order). Slots route through OmniRoute; combos are
created/seeded by the operator and only rebalanced by the orchestrator:

1. `trigger-quota-recalc-on-free-model-changes` — gate quota-research on a
   free-model-change trigger: (A) a new free/0-cost or free-provider model, or
   (B) an existing model whose free/0-cost status changed (either direction),
   both reachable via an existing connection. On trigger re-search ALL (OmniRoute
   `quotaTotal` as input, search sets hard-stop); skip otherwise. Trigger run
   adds gained-free models to fitting existing combos and drops lost-free ones on
   rebalance. Brings code to the existing `quota-research` spec. Depends on
   archived `update-combo-applier-to-rebalance-only` and
   `add-forecast-driven-quality-band`.
2. `register-new-free-models-in-omniroute` — register a new confirmed-free model
   reachable via an existing connection in OmniRoute (`POST /api/provider-models`,
   idempotent/additive/free-only); model outside our connections is skipped (no
   recalc, no registration); never creates connections. Extends the OmniRoute
   write surface (combos + additive registration only). Depends on
   `trigger-quota-recalc-on-free-model-changes` (2) and archived
   `update-combo-applier-to-rebalance-only`.


## Dropped (not needed for project essence)

- AA provider/detail/performance endpoints — the single free-tier endpoint
  (`GET /api/v2/language/models/free`) already provides every scoring input
  (`intelligence_index`, `coding_index`, `agentic_index`,
  `median_output_tokens_per_second`, `median_end_to_end_seconds`). YAGNI.
- models.dev retry/cache/ETag hardening — the orchestrator runs once per day, so
  ETag/conditional caching is pointless and retry is low-value; schema-drift
  reporting is already covered by `add-real-source-ingestion-tests`.
