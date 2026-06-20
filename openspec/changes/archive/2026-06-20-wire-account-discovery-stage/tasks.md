# Implementation Tasks (TDD)

Write each test first (red) → green → refactor. Mock only the network boundary
with **recorded real** responses (project.md → Testing Strategy). PostgreSQL is
**real**. OmniRoute shapes: `../OmniRoute` (`src/app/api/` connection &
rate-limit routes).

## Fixtures to record (real)

- OmniRoute connection / provider-account listing response.
- OmniRoute rate-limit availability response (present, and an unavailable/failed
  case).

## Tasks

- [x] 1. TEST: a new `account-discovery` stage calls `discover_live_accounts`
  with the OmniRoute client, groups pools, and persists pool membership +
  independence status through the repository; an adapter that returns success
  without writing pool rows fails the suite → implement the stage adapter.
- [x] 2. TEST: when the rate-limit fetch is unavailable the stage groups
  conservatively and promotes no connection to `confirmed` → implement
  conservative fallback wiring.
- [x] 3. TEST: the canonical pipeline includes `account-discovery` in order
  (after candidate discovery, before quota-sync/scoring) and `full` runs it →
  add the stage to `CANONICAL_STAGE_NAMES` / `build_canonical_stages`.
- [x] 4. TEST: CLI `discover-accounts` dispatches to the `account-discovery`
  stage (not `free-candidate-discovery`) and returns that stage's real outcome
  and exit code → update `_COMMAND_STAGE_NAMES`.
- [x] 5. TEST: allocation consumes confirmed-independence capacity so two
  same-provider accounts in one `assumed_shared` pool are not double-counted →
  verify against the oversubscription gate.
- [x] 6. Bind tests with `@pytest.mark.spec("...")`, drop matching lines from
  `tests/spec_coverage_pending.txt`, run full `pytest` and
  `openspec validate wire-account-discovery-stage --strict`.
