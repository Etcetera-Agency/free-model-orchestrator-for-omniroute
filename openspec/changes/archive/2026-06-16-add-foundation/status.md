# Status: IMPLEMENTED

Foundation implemented with TDD in `tests/test_foundation.py`.

- Schema runner applies `reference/db/schema.sql` to real ephemeral PostgreSQL.
- OmniRoute client adds auth/request ids and retries only idempotent GETs.
- Version gate permits read-only on unknown OmniRoute versions and blocks apply.
- Startup validation checks required config before any model endpoint call.
- State machine and apply precondition guards reject unsafe transitions/apply.
- Stable hashing supports idempotency keys.
- LLM prompt assembly loads external prompt files and redacts secrets.

Verification:

- `.venv/bin/python -m pytest tests/test_foundation.py -q`
- `openspec validate add-foundation --strict`
