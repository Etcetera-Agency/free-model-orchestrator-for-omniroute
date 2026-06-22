# OpenSpec TODO

## Deferred follow-up

- (none open)

## Active proposal slices (awaiting TDD implementation)

These were opened from the 2026-06-23 implementation review. Each carries
uncovered scenarios in `tests/spec_coverage_pending.txt` until its tests land.

- (none open)

## Resolved

- `fix-selection-correctness` — archived 2026-06-22. Production role scoring now
  uses AA metrics, latency source priority, health/stability telemetry, and
  missing-AA uncertainty instead of constant placeholders. Allocation now uses
  shared pool remaining and reserves pool capacity for every scored combo member.
- `harden-pipeline-resilience` — archived 2026-06-22. `partial_stale` no longer
  aborts later stages, quota research skips failed endpoints while persisting the
  rest, and apply requires fresh live-observed quota evidence above the
  configured positive safety-buffer floor.
- `add-rollback-idempotency` — archived 2026-06-22. Smoke-failure reverts and
  top-level rollback restores now send an `Idempotency-Key` derived from the
  restored combo model list.
- OmniRoute API bridge combo routes — DONE and deployed (2026-06-22). The fork
  exposes `GET /api/combos` and `GET|PUT /api/combos/fmo-*` on the bridge
  (OmniRoute commit `886ceb750`); `POST /api/combos/test` stays bridge `404` by
  design. Production `/opt/apps/omniroute` is pinned to `origin/main`
  (`a5a77e484`, image `omniroute:a5a77e484`) and verified live on
  `127.0.0.1:20129`: `GET /api/combos` → `401` (reaches OmniRoute auth, not a
  bridge `404`), `POST /api/combos/test` → `404`. Prod `apply`/`diff`/`full` can
  now reach combo management.

## Dropped (not needed for project essence)

- AA provider/detail/performance endpoints — the single free-tier endpoint
  (`GET /api/v2/language/models/free`) already provides every scoring input
  (`intelligence_index`, `coding_index`, `agentic_index`,
  `median_output_tokens_per_second`, `median_end_to_end_seconds`). YAGNI.
- models.dev cache/ETag hardening — the orchestrator runs once per day, so
  ETag/conditional caching is pointless (nothing to reuse between days).
  Schema-drift reporting is already covered by `add-real-source-ingestion-tests`.
