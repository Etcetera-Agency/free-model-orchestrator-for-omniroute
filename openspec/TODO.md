# OpenSpec TODO

## Active implementation queue

- update-quota-manager-binding-capacity: bind and implement quota-manager request-equivalent capacity scenarios.
- add-weekly-tpr-recalibration: bind and implement weekly tokens-per-request recalibration scenarios.
- add-auto-router-fallback-tail: bind and implement configured router tail scenarios.

## Deferred follow-up

None.

## Dropped (not needed for project essence)

- AA provider/detail/performance endpoints — the single free-tier endpoint
  (`GET /api/v2/language/models/free`) already provides every scoring input
  (`intelligence_index`, `coding_index`, `agentic_index`,
  `median_output_tokens_per_second`, `median_end_to_end_seconds`). YAGNI.
- models.dev retry/cache/ETag hardening — the orchestrator runs once per day, so
  ETag/conditional caching is pointless and retry is low-value; schema-drift
  reporting is already covered by `add-real-source-ingestion-tests`.
