# Project Context

## Purpose

**Free Model Orchestrator** — a standalone publisher that converts Hermes role
inventory and demand into `fmo-pools/v1` pool specs for OmniRoute. OmniRoute owns
free model discovery, model matching, probing, scoring, solving, combo apply,
runtime routing, fallback and retries.

**Core invariant:** FMO does not probe endpoints or write combos. It publishes
role policy and demand only; OmniRoute is the model/capacity source of truth.

The main process runs once per day (daily batch); ad-hoc runs are manual or
event-driven.

## Tech Stack

- PostgreSQL (schema in `reference/db/schema.sql`, migrations in `reference/db/migrations/`)
- Python services calling the OmniRoute OpenAI-compatible / management API
- `Instructor` + Pydantic only for Hermes role inspection and intelligence
  hints. Deterministic code owns publish validation.
- OmniRoute as the upstream gateway and pool-contract owner (`/api/fmo/pools`,
  `/api/fmo/usage`, role combo runtime after solve/apply).

## Project Conventions

### Code Style

- Deterministic code owns inventory validation, demand forecasts, pool payload
  construction, idempotency, and publish/audit records.
- LLM steps only produce structured Hermes role hints; they are never a source
  of truth for model selection.

### Architecture Patterns

- Unit of FMO management is a Hermes role plus its consumers and demand.
- Pool publication is idempotent by payload hash.
- OmniRoute owns provider endpoint identity, combo solving, apply, smoke, and
  rollback.

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

- Never write OmniRoute combos directly from FMO.
- Never probe provider/model endpoints from FMO.
- Do not keep local provider/model/capacity caches as a fallback source.

## External Dependencies

- **OmniRoute** — gateway and pool contract owner.
- **Hermes** — role registry + demand source (`~/.hermes/cron/jobs.json`,
  `~/.hermes/state.db`); consumes the combos but is not part of this service.
