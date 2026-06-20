# OpenSpec TODO

## Active Slice Backlog

- `wire-demand-forecast-and-role-lifecycle`: implement and bind executable
  coverage for forecast-derived demand, cold-start floors, role removal grace,
  reactivation, new-role bootstrap, and reconcile/forecast-before-allocation
  ordering.

## Dropped (not needed for project essence)

- AA provider/detail/performance endpoints — the single free-tier endpoint
  (`GET /api/v2/language/models/free`) already provides every scoring input
  (`intelligence_index`, `coding_index`, `agentic_index`,
  `median_output_tokens_per_second`, `median_end_to_end_seconds`). YAGNI.
- models.dev retry/cache/ETag hardening — the orchestrator runs once per day, so
  ETag/conditional caching is pointless and retry is low-value; schema-drift
  reporting is already covered by `add-real-source-ingestion-tests`.
