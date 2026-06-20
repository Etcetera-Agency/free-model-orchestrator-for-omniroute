# Implementation Tasks (TDD)

Write each test first (red) → green → refactor. Mock only the network boundary
with **recorded real** responses (project.md → Testing Strategy). PostgreSQL is
**real**. OmniRoute shapes: `../OmniRoute` (`src/app/api/`, `/v1` chat handler).

## Fixtures to record (real)

- OmniRoute `POST /v1/chat/completions` success body (OpenAI shape:
  `choices[0].message.content` non-empty, no top-level `status_code`).
- OmniRoute `POST /v1/chat/completions` empty/refusal body
  (`choices[0].message.content` empty or missing).
- OmniRoute non-2xx HTTP response (so `OmniRouteClient` raises
  `OmniRouteRequestError`).

## Tasks

- [x] 1. TEST: `_smoke_combo` returns `True` for a real OpenAI-shaped body with
  non-empty `choices[0].message.content` and never reads a body-level
  `status_code` → implement body parsing.
- [x] 2. TEST: `_smoke_combo` returns `False` when the completion body has empty
  or missing assistant content → implement empty-content handling.
- [x] 3. TEST: `_smoke_combo` returns `False` (and apply rolls back) when the
  smoke POST raises `OmniRouteRequestError` (non-2xx HTTP) → wrap the smoke POST
  so the error maps to a smoke failure, not a crash.
- [x] 4. TEST: production apply commits a combo when the recorded real smoke body
  is valid (end-to-end apply stage, real Postgres) → verify no spurious rollback.
- [x] 5. Replace fabricated `{"status_code": ..., "content": ...}` smoke shapes
  in `tests/test_composition.py` / `tests/test_advisory.py` with the recorded
  real bodies; keep probe-path fixtures consistent with the real probe shape.
- [x] 6. Bind tests with `@pytest.mark.spec("combo-applier::...")`, drop the
  matching lines from `tests/spec_coverage_pending.txt`, run full `pytest`.
