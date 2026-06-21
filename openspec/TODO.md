# OpenSpec TODO

No deferred review follow-up work discovered.

## Active proposal slices (pending TDD implementation)

Each slice carries uncovered scenarios listed in
`tests/spec_coverage_pending.txt`. Bind a test, drop the matching line, then
archive when implemented.

Hermes per-profile + auxiliary model slots → combos (proposed, remaining in
requested implementation order). Slots route through OmniRoute; combos are
created/seeded by the operator and only rebalanced by the orchestrator:

1. `register-new-free-models-in-omniroute` — register a new confirmed-free model
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
