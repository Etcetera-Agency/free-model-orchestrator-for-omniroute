# OpenSpec TODO

## Deferred follow-up

- Implement active pool migration changes after approval: publish
  `fmo-pools/v1` with payload-hash idempotency first, then remove FMO
  quota/matching/probing/allocation/apply modules only after OmniRoute shadow
  solve, atomic apply, and single-writer cutover are verified.
  Gate audit 2026-06-29: FMO publisher slice is archived and pushed, but
  destructive removal remains blocked. Production `etc2nd-shlink`
  `127.0.0.1:20129` returns bridge `404` for `/api/fmo/pools` and
  `/api/fmo/usage`; `127.0.0.1:20128` refused connection from the same shell.
  Local OmniRoute repo still has unimplemented active proposals
  `add-fmo-pools-contract`, `add-fmo-pools-planning`,
  `add-fmo-pools-solve-tail`, and `add-fmo-pools-apply`. Do not remove FMO
  quota/matching/probing/allocation/apply until those OmniRoute slices are live
  and the single-writer cutover is verified.

- Server-side default combo grid bootstrap — separate deploy task. Regenerate
  seed models with the live FMO matcher, back up `GET /api/combos`, then create
  the default one-seed combos from `docs/combo-grid-bootstrap.md` on OmniRoute.
- Continue post-deploy quota/access verification after the `/v1/search` query
  length fix. The previous `research-quotas --dry-run` `http_error` was caused
  by 716-character quota queries exceeding OmniRoute's 500-character schema
  limit; active quota rules and eligible endpoints are now present, but provider
  coverage still needs broadening beyond the current Nvidia seed path.
- Add group-pattern quota topology support for providers whose free tier varies
  by model family/group (for example Antigravity-style pools). Current live fix
  fails such provider/account answers closed instead of widening them to
  `model_pattern='*'`; next work should extract stable model patterns, store
  narrower quota rules, and teach access classification to match those patterns.
- Fix OmniRoute `gemini-grounded-search` provider configuration. Live
  `/v1/search` succeeds through default routing (`exa-search`) but pinned
  `provider='gemini-grounded-search'` returns HTTP 429 even for `hello world`;
  FMO now has a fallback, but the intended grounded-search provider still needs
  platform-side setup/repair.
- Investigate Nvidia per-model timeouts through OmniRoute's model-test route.
  On 2026-06-24, live `POST /api/models/test` with the active Nvidia
  connection timed out after 20s for `nvidia/z-ai/glm-5.1` and
  `nvidia/minimaxai/minimax-m2.7`; after FMO `e3ecf74` deployed, the
  model-test-backed `sweep-provider-models` command reproduced the same timeout
  for both models at offsets 125 and 45. Nvidia was later disabled in OmniRoute,
  so FMO must not use cached Nvidia rows while the provider is inactive. If
  Nvidia is re-enabled, rerun OmniRoute `/api/models/test-all` on Nvidia batches
  to separate upstream outage, queue timeout, and per-model failures.
## Resolved

- Nvidia/provider model sweep tooling — deployed 2026-06-24, then corrected to
  use OmniRoute's per-model test API in FMO `e3ecf74`. FMO `be61cf7` added the
  explicit `sweep-provider-models` operator command with provider, limit,
  offset, delay, timeout, dry-run, force, JSON, and live flushed progress logs.
  The follow-up correction changes the command from an FMO-only raw chat probe
  to `/api/models/test`, passing stored provider/model/connection identity so
  sweep evidence matches OmniRoute UI/test-all behavior. Live verification after
  the corrected deploy: `codestral/codestral-latest` passed; the two
  user-flagged Nvidia models timed out through the same corrected model-test
  path.
- Live OmniRoute catalog preflight — FMO now refreshes active provider/account
  and model availability from OmniRoute before decision commands and scheduled
  pipelines use cached rows. Disabled or absent providers/accounts are marked
  disabled, inactive or absent active models are tombstoned, reappearing models
  clear tombstones, and downstream stages ignore disabled/tombstoned rows.
- Live combo rebalance readiness — deployed 2026-06-24. The live server is on
  FMO `f0cf757`; provider/model endpoint duplicates are removed, target Nvidia
  aliases bind to canonical AA slugs, active quota rules exist, two endpoints
  have passed probes, allocation produces non-duplicated targets for
  `fmo-grid-aux-text` and `fmo-grid-int-med`, real `apply` exits successfully
  with streaming combo smoke, degraded empty-target combos are skipped without
  destructive writes, and final `full --dry-run` exited successfully with
  `unmanaged_combos=[]`. Later Nvidia provider sweep evidence supersedes the
  old seed probe state; current Nvidia availability is tracked in the deferred
  repair item above.
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
