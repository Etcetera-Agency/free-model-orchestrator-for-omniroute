# OpenSpec TODO

No deferred review follow-up work discovered.

## Active proposal slices (pending TDD implementation)

Each slice carries uncovered scenarios listed in
`tests/spec_coverage_pending.txt`. Bind a test, drop the matching line, then
archive when implemented.

- `wire-account-discovery-stage` — `account-discovery` module is unit-tested but
  never wired into the pipeline; `discover-accounts` runs a catalog scan.
- `integrate-quality-and-context-gates` — `quality-gate` and
  `context-window-eligibility` hard filters are not applied in production
  scoring.

## Dropped (not needed for project essence)

- AA provider/detail/performance endpoints — the single free-tier endpoint
  (`GET /api/v2/language/models/free`) already provides every scoring input
  (`intelligence_index`, `coding_index`, `agentic_index`,
  `median_output_tokens_per_second`, `median_end_to_end_seconds`). YAGNI.
- models.dev retry/cache/ETag hardening — the orchestrator runs once per day, so
  ETag/conditional caching is pointless and retry is low-value; schema-drift
  reporting is already covered by `add-real-source-ingestion-tests`.
