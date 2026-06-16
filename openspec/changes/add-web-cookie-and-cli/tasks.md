# Implementation Tasks (TDD)

Write each test first (red) → green → refactor. Mock only the network boundary
with **recorded real** responses (project.md → Testing Strategy). PostgreSQL is
**real**. OmniRoute shapes: `../OmniRoute`.

## Fixtures to record (real)

- A web-cookie provider connection from OmniRoute `/api/providers` (auth_type web cookie).
- A basic-text probe response, plus a login/challenge page response (probe failure).
- An expired-session response for the daily session-health check.

## Tasks

- [ ] 1. TEST: web-cookie endpoints come only from connection/static/manual/previously-confirmed sources; daily refresh does not auto-discover them → implement sourcing.
- [ ] 2. TEST: default capabilities are text-only; a tool/JSON/vision role excludes the endpoint; capability raised only after a confirmed probe → implement capability gate.
- [ ] 3. TEST: basic-text probe passes on plain text, fails on a login/challenge page; expired session → `unavailable` → implement probe + session health.
- [ ] 4. TEST: fallback-only (not primary without override); unknown quota → opportunistic, never guaranteed → implement weight/quota policy.
- [ ] 5. TEST: CLI exposes per-stage + `full`/`diff`/`apply`/`rollback`/`aa-index *` + diagnostics; flags parsed → implement CLI.
- [ ] 6. TEST: exit codes (0/2/3/4/5/6/7) — unsafe apply returns 5 and changes nothing → implement exit-code mapping.
- [ ] 7. TEST: `--dry-run` validates the combo locally and never calls `/api/combos/test` → implement dry-run.
