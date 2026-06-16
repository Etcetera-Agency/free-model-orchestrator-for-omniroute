# Completion Review: add-foundation

Completion of P1: 100%* — real ephemeral PostgreSQL applies `reference/db/schema.sql`; expected foundation tables asserted.
Completion of P2: 100%* — OmniRoute client adds auth and `X-Request-Id`, retries GET 429 with `Retry-After`, and does not retry POST apply.
Completion of P3: 100%* — version gate allows read-only and forbids apply for unknown versions.
Completion of P4: 100%* — startup validation fails on bad cron or missing required env before model endpoint checks.
Completion of P5: 100%* — forbidden endpoint and combo transitions are rejected.
Completion of P6: 100%* — apply guard refuses missing DB/snapshot/validation/quota/probe preconditions.
Completion of P7: 100%* — stable canonical hashes detect unchanged inputs and changed ordered inputs.
Completion of P8: 100%* — LLM site config loads external prompts, omits secret context keys, and redacts secret-shaped text.

Code Simplifier:

- Ran simplification pass on touched foundation code.
- Tightened package runtime to Python 3.12 to match isolated project venv and current annotations.
- Fixed test fixture reliability: short PostgreSQL socket path, UTF-8 initdb, isolated `.venv`.

Verification:

- `.venv/bin/python -m pytest tests/test_foundation.py -q` — 13 passed.
- `openspec validate add-foundation --strict` — valid.
