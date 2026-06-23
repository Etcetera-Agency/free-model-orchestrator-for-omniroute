# OpenSpec TODO

## Deferred follow-up

- Server-side default combo grid bootstrap — separate deploy task. Regenerate
  seed models with the live FMO matcher, back up `GET /api/combos`, then create
  the default one-seed combos from `docs/combo-grid-bootstrap.md` on OmniRoute.
- Verify post-deploy combo rebalance readiness on the live FMO server. The
  identity fix makes live `fmo-grid-*` combos visible and avoids `fmo-fmo-*`, but
  current production state still has zero confirmed endpoints, zero probes, and
  empty allocation targets, so `apply --dry-run` remains blocked by apply
  preconditions.
- Continue post-deploy quota/access verification after the `/v1/search` query
  length fix. The previous `research-quotas --dry-run` `http_error` was caused
  by 716-character quota queries exceeding OmniRoute's 500-character schema
  limit; after deploy, confirm quota rules are written, then clear downstream
  `classify-access` / probe blockers until endpoints become eligible.
- Add group-pattern quota topology support for providers whose free tier varies
  by model family/group (for example Antigravity-style pools). Current live fix
  fails such provider/account answers closed instead of widening them to
  `model_pattern='*'`; next work should extract stable model patterns, store
  narrower quota rules, and teach access classification to match those patterns.
## Resolved

- `update-aa-index-migration-inspector` — archived 2026-06-23. AA migration
  now renders the external prompt file with deterministic migration context,
  leaves model selection to the shared resolver, normalizes proposals to typed
  `threshold_value`, validates operational errors with bounded repair attempts,
  persists baseline/attempt reports, and revalidates rollout against current
  repository state before threshold mutation. Full pytest deferred to final
  all-slice verification by request.
- `update-smart-combo-review-context` — archived 2026-06-23. Reviewer calls
  now receive deterministic current/target/diff context plus role, demand,
  allocation, candidate, quota, diversity, validation, and apply-precondition
  facts through the external prompt file. Candidate details are bounded and
  secret-like values are redacted. Reviewer output remains advisory only and
  does not alter the applied deterministic diff. Full pytest deferred to final
  all-slice verification by request.
- `update-combo-member-identity` — archived 2026-06-23. Allocation targets
  now carry structured OmniRoute model steps, account/quota-pool/canonical
  identity, and diversity diagnostics; diff/apply persist structured members
  with endpoint-id audit fields; apply sends structured `PUT /api/combos/{id}`
  payloads while preserving drift, safety, smoke, and rollback gates. Full
  pytest deferred to final all-slice verification by request.
- `update-quota-research-range-resolution` — archived 2026-06-23. Quota
  research now threads `previous_limit` into the
  Instructor inspector prompt, documents deterministic range clamping in the
  prompt template, asks search for cumulative request/token budgets across
  official and community sources, and keeps worsened-quota safe mode under the
  deterministic activation gate. Shared Inspector model resolution is finished:
  every Inspector leaves `LlmSiteConfig.model` unset, uses configured prompt
  files, requires resolver-selected concrete provider models, fails closed as
  `llm_model_unavailable` without one, skips stale/exhausted/locked live quota,
  and no repo text retains fabricated Inspector route ids.
- `add-intelligence-inspector` — archived 2026-06-23. Hermes now runs a second
  advisory intelligence Inspector per describing unit, caches verdicts by content
  hash, maps axis/tier to quality anchors, fills forecast model-choice metadata,
  persists role quality anchors, and resolves reusable/default combo grid cells
  deterministically. The concrete live server combo bootstrap remains a deferred
  deploy task above.
- `refactor-collapse-stage-helper-aliases` — archived 2026-06-23. Removed the
  slug/hash/quota-math re-export aliases from `composition_stages/_helpers.py`,
  repointed drained stage modules to canonical `idempotency`/`quota_normalize`
  imports, and removed the root shim alias exports. Full pytest is green under
  both entry points.
- `refactor-drain-stages-apply` — archived 2026-06-23. Back-of-pipeline stage
  bodies now live in `allocation.py`, `apply.py`, `rollback.py`, and `audit.py`;
  shared stage dataclasses/adapter builder live in `_base.py`, cross-cluster
  helpers live in `_helpers.py`, and `_legacy.py` is deleted. Focused stage/spec
  docs checks, `make check`, and OpenSpec validation are green; full pytest is
  deferred to the final all-slice verification pass.
- `refactor-drain-stages-runtime` — archived 2026-06-23. Middle-of-pipeline
  stage bodies and role-scoring helpers now live in `probing.py`, `telemetry.py`,
  `inventory.py`, and `roles.py`. Focused runtime/spec docs checks,
  `make check`, and OpenSpec validation are green.
- `refactor-drain-stages-discovery` — archived 2026-06-23. Front-of-pipeline
  stage bodies now live in `discovery.py`, `quota.py`, and `access.py`; adapter
  re-exports remain stable. Focused discovery/quota/access/spec docs checks,
  `make check`, and OpenSpec validation are green.
- `refactor-unify-shared-helpers` — archived 2026-06-23. Row helpers remain
  canonical in `persistence/_base.py`; `utcnow`, slug/hash, and idempotency-key
  helpers now live in `idempotency.py`; quota payload math lives in
  `quota_normalize.py`; and production call sites import those canonical
  definitions. `make check`, OpenSpec validation, and full pytest under both
  entry points are green.
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
- Live quota research follow-up — many OmniRoute free models return useful
  search summaries but no numeric daily/monthly amount, and their live
  `/api/usage/quota` rows may expose only liveness (`percentRemaining`) without
  `quotaTotal`. Keep those endpoints fail-closed as `quota_rule_missing` while
  allowing endpoints with active rules to classify/probe/allocate. Main quota
  research is provider/account scoped; add calibration or provider-specific
  quota sources for silent provider pools before treating them as usable
  capacity.
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
