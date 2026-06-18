# OpenSpec TODO

No deferred foundation work discovered.
No deferred edge-case test coverage work discovered.
No deferred external metadata fetcher work discovered.

## Moved to change proposals

Every previously deferred item is now tracked as a change proposal under
`openspec/changes/`. The "Replace hand-built test payloads" item is folded into
each ingestion slice's fixtures task for its boundary.

- `add-real-source-ingestion-tests` (active) — models.dev real top-level
  provider-keyed shape + schema-drift; Artificial Analysis free-tier production
  ingestion (`/api/v2/language/models/free`, pagination, legacy endpoints
  unavailable); realistic fixtures for the OmniRoute, models.dev and Artificial
  Analysis boundaries.
- `add-hermes-inventory-real-shapes` (archived) — real Hermes source-shape
  parsers (`cron/jobs.json`, `webhook_subscriptions.json`, `hermes profile list`,
  `state.db` sessions) and hermes fixtures.
- `finish-hermes-inventory-adapters` — command/http adapters, live profile
  enumeration, `service` from gateway config, live-deployment fixtures.
- `add-omniroute-catalog-ingestion` — real OmniRoute provider/model catalog fetch.
- `add-omniroute-free-registry-ingestion` — real free-model registry fetch + drift.
- `add-omniroute-account-ingestion` — real connections/account/rate-limit fetch.
- `add-live-quota-ingestion` — live quota fetch + stale/unavailable handling.
- `add-telemetry-ingestion` — live usage/latency/failure/trace fetch.
- `add-quota-research-ingestion` — production `/v1/search` quota research client.
- `add-web-cookie-acquisition` — real session acquisition + live health probes.
- `add-instructor-runtime-adapter` — shared Instructor + Pydantic runtime for the
  four structured-LLM sites.
- `add-web-cookie-acquisition` — acquire usable web-cookie/browser sessions (the
  means to actually obtain these providers as reduced-weight free capacity) with
  live health probes and failure-mode classification.

## Dropped (not needed for project essence)

- AA provider/detail/performance endpoints — the single free-tier endpoint
  (`GET /api/v2/language/models/free`) already provides every scoring input
  (`intelligence_index`, `coding_index`, `agentic_index`,
  `median_output_tokens_per_second`, `median_end_to_end_seconds`). YAGNI.
- models.dev retry/cache/ETag hardening — the orchestrator runs once per day, so
  ETag/conditional caching is pointless and retry is low-value; schema-drift
  reporting is already covered by `add-real-source-ingestion-tests`.

## Deferred Work

None — all items above have been moved into change proposals.
