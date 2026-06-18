# Project Context

## Purpose

**Free Model Orchestrator** — a standalone service that keeps the set of
no-cost-usable models in OmniRoute up to date. It discovers, verifies and
allocates models that can be used without monetary charges (zero-price models,
paid models reachable inside a confirmed provider free quota, and temporary
promo/free-tier models), then builds and updates per-role combos. OmniRoute
itself executes runtime routing, fallback and retries; this service does not
participate in request runtime.

**Core invariant:** no probe or production request may exceed confirmed free
capacity. If free access cannot be confirmed or safely bounded, the endpoint is
not used.

The main process runs once per day (daily batch); ad-hoc runs are manual or
event-driven.

## Tech Stack

- PostgreSQL (schema in `reference/db/schema.sql`, migrations in `reference/db/migrations/`)
- Python services calling the OmniRoute OpenAI-compatible / management API
- `Instructor` + Pydantic for all structured-LLM steps — no separate agent
  framework. There are exactly **four** Instructor/LLM call sites:
  1. quota-research inspector (`add-quota`) — extracts quota from search;
  2. Hermes role Inspector forecast (`hermes-inventory`) — demand estimate;
  3. smart-combo-reviewer (`add-advisory-llm`) — advisory combo diffs;
  4. aa-index migration agent (`add-advisory-llm`) — threshold proposals.

  All four are part of the project. Sites 3–4 are **advisory / fail-open**: if
  the LLM is unavailable or returns nothing usable, the deterministic pipeline
  proceeds without it. Nothing here is out-of-scope or skippable.
- OmniRoute as the upstream gateway (`/v1/*` OpenAI-compatible, `/api/*` management,
  `/v1/search` for quota research via `gemini-grounded-search`)
- External data: models.dev catalog (`api.json` / `catalog.json`), Artificial
  Analysis `/api/v2/language/models`

## Project Conventions

### Code Style

- Deterministic code owns validation, capacity checks, dry-run and rollout.
- LLM steps only produce structured proposals; they are never a source of truth.
- Every external fetch is stored as an immutable, content-hashed snapshot.

### Architecture Patterns

- Unit of management is the `provider_endpoint` (provider account + model id),
  not the canonical model.
- One combo per role; combos are broad (many independent endpoints) so OmniRoute
  absorbs intraday failures without a rebuild.
- Global quota allocation across all roles (not per-role independent build).
- Minimal-diff apply with snapshot + audit + rollback.
- Idempotency keys per stage (catalog/quota/probe/combo) — see
  `reference/docs/architecture/00-system-flow.md`.

### Testing Strategy

**TDD is mandatory.** For every task: write the failing test first (red), then
the minimum code to pass (green), then refactor. Each change's `tasks.md` is
ordered test-before-implementation. A capability requirement's `#### Scenario`
blocks are the acceptance tests — encode them.

**Scenarios are executable and the binding is enforced.** Bind each test to the
scenario it encodes with `@pytest.mark.spec("<capability>::<Scenario name>")`,
and remove that scenario from `tests/spec_coverage_pending.txt`. The
`tests/test_spec_coverage.py` gate (part of the normal `pytest` run) fails the
build when a scenario has no test and is not on the pending allowlist, when a
marker points at a non-existent scenario, or when a pending entry is stale or
already covered. The pending allowlist must shrink over time, never grow — a new
change's scenarios are bound as its tests land, before it is archived.

**Mock realistically — never hand-fabricate payload shapes.** Mock only the
network boundary, and only with responses recorded from the real services:

- **OmniRoute** — record real JSON from a running instance, or copy exact shapes
  from the OmniRoute source, which is checked out alongside this repo at
  `../OmniRoute` (relative to the package root). Authoritative shape sources:
  `open-sse/handlers/search.ts` (`SearchResponse`/`SearchResult` for `/v1/search`),
  `open-sse/config/searchRegistry.ts` (provider ids incl. `gemini-grounded-search`),
  and the `/api/*` route handlers under `src/app/api/`. Do not invent `/api/*` or
  `/v1/*` response fields.
- **models.dev** — record a trimmed real `api.json`/`catalog.json` slice
  (provider→model with real `cost`); cover a zero-cost, a priced, and a
  no-`cost` entry.
- **Artificial Analysis** — record one real `/api/v2/language/models` item
  (fields under `evaluations`: `artificial_analysis_*`).
- **Hermes inventory** — record real `~/.hermes/cron/jobs.json` and `state.db`
  shapes from `NousResearch/hermes-agent` (`cron/jobs.py`, profiles, webhook subs).
- **LLM / Instructor** — record representative structured completions (valid AND
  malformed) and assert the deterministic validator/repair path; never call a
  live model in unit tests.

**Do NOT mock PostgreSQL.** Use a real ephemeral instance (e.g. `initdb` into a
tmp dir, apply `reference/db/schema.sql`) so schema, FKs and CHECK constraints
are exercised for real.

- Acceptance criteria live per module in `reference/docs/modules/*`.
- Test plan: `reference/tests/test-plan.md`.

### Git Workflow

- Change-ids kebab-case, verb-led (`add-`, `update-`, `remove-`, `refactor-`).
- Specs in `openspec/specs/` are the living truth; changes go through
  `openspec/changes/<id>/` with delta specs.

## Domain Context

The authoritative legacy specification (v3.19) is copied, self-contained, into
`reference/` — the OpenSpec capabilities here are distilled from those modules.
Tunable values (combo size, reserves, multipliers, percentiles) live in
`reference/config/config.example.yaml`; specs reference those keys rather than
restating numbers.

Status vocabulary (single canonical set, used for quota independence and
attribution): `confirmed | inferred | assumed_shared | unknown`.

## Important Constraints

- Never exceed confirmed free capacity (the core invariant above).
- `require_hard_stop` and `exclude_unknown` gate endpoints lacking a safe bound.
- Multiple accounts of one provider are NOT independent capacity unless
  `confirmed`.
- Quota research summary-sourced rules are capped (`summary_confidence_cap`) and
  treated as opportunistic capacity.

## External Dependencies

- **OmniRoute** — gateway; management API (`/api/providers`, `/api/free-models`,
  `/api/free-provider-rankings`, `/api/free-tier/summary`, `/api/rate-limits`),
  search (`/v1/search`), OpenAI-compatible chat (`/v1`).
- **models.dev** — free-candidate catalog; cost lives per provider→model.
- **Artificial Analysis** — intelligence/coding/agentic indices + speed metrics.
- **Hermes** — role registry + demand source (`~/.hermes/cron/jobs.json`,
  `~/.hermes/state.db`); consumes the combos but is not part of this service.
