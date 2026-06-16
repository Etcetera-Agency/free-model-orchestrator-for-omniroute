# Implementation Tasks (TDD)

Write each test first (red) → minimum code to pass (green) → refactor. Mock only
the network boundary with **recorded real** responses (see project.md → Testing
Strategy). PostgreSQL is **real** (ephemeral `initdb` + `reference/db/schema.sql`),
never mocked. OmniRoute shapes: `../OmniRoute`.

## Fixtures to record (real)

- OmniRoute health/version response (for the version handshake) — known and unknown version.
- A GET returning `429` with a `Retry-After` header.
- `reference/db/schema.sql` applied to a throwaway Postgres.

## Tasks

- [ ] 1. TEST: `schema.sql` applies cleanly on a real ephemeral Postgres (tables, FKs, CHECKs) → wire migration runner for `reference/db/migrations/`.
- [ ] 2. TEST: OmniRoute client adds auth + `X-Request-Id`, retries only idempotent GET, honors `Retry-After` (recorded 429) → implement client.
- [ ] 3. TEST: unknown OmniRoute version (recorded handshake) allows read-only, forbids apply → implement version gate.
- [ ] 4. TEST: startup validation fails on bad cron / missing required env and does NOT call model endpoints → implement startup validation.
- [ ] 5. TEST: each forbidden state transition is rejected (excluded_unknown→active, quota_exhausted→active, probe_failed→active, planned→applied) → implement state machines.
- [ ] 6. TEST: apply is refused when snapshot/DB/validation/quota/probe precondition fails → implement apply preconditions.
- [ ] 7. TEST: re-running with unchanged inputs produces no combo change and skips unchanged probes → implement idempotency keys.
- [ ] 8. TEST: `llm` loader resolves shared defaults + per-site model selection and loads each site's external prompt file; prompt assembly contains no secrets → implement loader + redaction helper.
