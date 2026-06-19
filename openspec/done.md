# OpenSpec Done

## Archived change proposals

Every previously deferred ingestion/test-shape item has been completed and
archived under `openspec/changes/archive/`. The "Replace hand-built test
payloads" item was folded into each ingestion slice's fixtures task for its
boundary.

- `add-real-source-ingestion-tests` (archived) — models.dev real top-level
  provider-keyed shape + schema-drift; Artificial Analysis free-tier production
  ingestion (`/api/v2/language/models/free`, pagination, legacy endpoints
  unavailable); realistic fixtures for the OmniRoute, models.dev and Artificial
  Analysis boundaries.
- `add-hermes-inventory-real-shapes` (archived) — real Hermes source-shape
  parsers (`cron/jobs.json`, `webhook_subscriptions.json`, `hermes profile list`,
  `state.db` sessions) and hermes fixtures.
- `finish-hermes-inventory-adapters` (archived) — command/http adapters, live
  profile enumeration, `service` from gateway config, live-deployment fixtures.
- `add-omniroute-catalog-ingestion` (archived) — real OmniRoute provider/model
  catalog fetch.
- `add-omniroute-free-registry-ingestion` (archived) — real free-model registry
  fetch + drift.
- `add-omniroute-account-ingestion` (archived) — real connections/account/rate-limit
  fetch.
- `add-live-quota-ingestion` (archived) — live quota fetch + stale/unavailable
  handling.
- `add-telemetry-ingestion` (archived) — live usage/latency/failure/trace fetch.
- `add-quota-research-ingestion` (archived) — production `/v1/search` quota
  research client.
- `add-web-cookie-acquisition` (archived) — acquire usable web-cookie/browser
  sessions (the means to actually obtain these providers as reduced-weight free
  capacity) with live health probes and failure-mode classification.
- `add-instructor-runtime-adapter` (archived) — shared Instructor + Pydantic
  runtime for the four structured-LLM sites.
- `compose-production-pipeline` (archived) — production composition root for CLI
  stage execution and repository-backed diagnostics.
- `persist-metadata-sync` (archived) — repository persistence for models.dev and
  Artificial Analysis metadata sync output.
- `derive-apply-preconditions` (archived) — repository-backed apply guard
  preconditions at entrypoint.
- `run-scheduler-process` (archived) — `serve` scheduler entrypoint and
  persistent run-lock routing.
- `migrate-discovery-writers-to-repository` (archived) — scanner and
  free-registry persistence now write provider/account/catalog, endpoint,
  registry snapshot, and free-model rows through repository methods; source
  regression tests reject embedded table SQL in those stage modules.
- `wire-production-stage-modules` (archived) — production composition dispatches
  `sync-free-registry` and `scan-providers` through registry/scanner adapters,
  invokes every canonical stage through an adapter-backed boundary during
  `full`, and rejects the old unconditional success placeholder helper.
