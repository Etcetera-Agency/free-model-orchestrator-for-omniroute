# OpenSpec TODO

## Deferred follow-up

- Live OmniRoute API bridge on etc2nd-shlink (`127.0.0.1:20129`) still returns
  bridge-level 404 for `/api/combos*`; FMO combo apply reads `/api/combos` and
  posts `/api/combos/{id}`. Decide whether production FMO should use a different
  OmniRoute base URL for combo apply or whether the bridge must explicitly allow
  the required combo management routes.

## Dropped (not needed for project essence)

- AA provider/detail/performance endpoints — the single free-tier endpoint
  (`GET /api/v2/language/models/free`) already provides every scoring input
  (`intelligence_index`, `coding_index`, `agentic_index`,
  `median_output_tokens_per_second`, `median_end_to_end_seconds`). YAGNI.
- models.dev retry/cache/ETag hardening — the orchestrator runs once per day, so
  ETag/conditional caching is pointless and retry is low-value; schema-drift
  reporting is already covered by `add-real-source-ingestion-tests`.
