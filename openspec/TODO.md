# OpenSpec TODO

## Deferred follow-up

- (none open)

## Active proposal slices (awaiting TDD implementation)

These were opened from the 2026-06-23 implementation review. Each carries
uncovered scenarios in `tests/spec_coverage_pending.txt` until its tests land.

### Refactor program (2026-06-23 static-analysis review)

Behavior-preserving structure work; the existing pytest suite is the
behavior-preservation oracle for every slice. All add structural requirements to
the `system-architecture` capability. Implement in order — each depends on the
package/shim the previous one establishes.

- `refactor-unify-shared-helpers` — deduplicate row helpers, `utcnow`, slug/hash/
  idempotency-key builders, and quota-math helpers into one canonical home each,
  now that the target modules exist.

Final verification after the last active slice: run the full suite once through
both `.venv/bin/pytest` and `.venv/bin/python -m pytest`.

Type-error triage (66 pyright errors) and the import-path fix are folded into the
slices that own the affected modules rather than tracked as separate scenarios.

## Resolved

- `refactor-extract-test-fakes` — archived 2026-06-23. Shared composition fakes
  now live in `tests/_clients.py`, shared helpers live in
  `tests/_composition_support.py`, composition coverage is split across
  per-domain test files, and `tests` is importable from both pytest entry
  points. Focused split composition/spec docs checks are green under both entry
  points.
- `refactor-split-stages-apply` — archived 2026-06-23. Demand forecast,
  allocation, diff/apply, rollback, audit, and cross-cluster stage helpers now
  resolve through dedicated `composition_stages` modules. Focused
  allocation/advisory/composition docs tests and `make check` are green.
- `refactor-split-stages-runtime` — archived 2026-06-23. Probing, telemetry,
  Hermes inventory, role lifecycle, role scoring, and the role-scoring helper
  cluster now resolve through dedicated `composition_stages` modules. Focused
  role/telemetry/inventory/composition tests and `make check` are green.
- `refactor-split-stages-discovery` — archived 2026-06-23.
  `fmo.composition_stages` is now a package with discovery, quota, and access
  cluster modules plus a shim preserving existing composition imports and
  adapter wiring. Focused discovery/quota/composition tests and `make check` are
  green.
- `refactor-split-persistence` — archived 2026-06-23. `fmo.persistence` is now a
  package with `_base.py` plus per-aggregate repository modules, while
  `__init__.py` keeps the public import surface stable. Persistence package
  pyright, ruff/format, vulture, focused persistence tests, and spec coverage are
  green.
- `prefer-learned-quota-with-liveness` — archived 2026-06-23. Live OmniRoute
  `quotaTotal`/`quotaUsed` are now stored as a learned sub-day request-rate
  signal, not a daily budget; quota sync persists `percentRemaining`/lockout
  liveness without overwriting research/calibration capacity. Apply now requires
  confirmed-free, hard-stop, fresh probe, known daily budget above buffer, fresh
  liveness above floor, and no lockout; null `resetAt` is healthy.
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
