# Completion Review: add-advisory-llm

Completion of P1: 100%* — reviewer performs one structured call and rejects forbidden operations.
Completion of P2: 100%* — diffs apply independently on a copy; invalid diffs are logged/skipped without repair loop.
Completion of P3: 100%* — reviewer failure/no-valid-diffs fails open and never calls `/api/combos/test`.
Completion of P4: 100%* — index-version change freezes old thresholds, preserves combos, creates migration state, and stops production recalculation.
Completion of P5: 100%* — migration model selection chooses highest available new intelligence index and calls structured proposal fn.
Completion of P6: 100%* — deterministic validation checks version, metric, combo size, quota, quality, and approval gate.
Completion of P7: 100%* — no model returns waiting state and invalid/smoke-risk proposals leave production unchanged or fail validation.

Code Simplifier:

- Ran simplification pass on touched advisory code.
- Kept smart review and AA migration separated behind deterministic validators.

Verification:

- `.venv/bin/python -m pytest tests/test_advisory.py tests/test_role_lifecycle.py tests/test_allocation.py tests/test_scoring.py tests/test_quota.py tests/test_discovery.py tests/test_foundation.py -q` — 52 passed.
- `/Users/theDay/.nvm/versions/node/v24.1.0/bin/openspec validate add-advisory-llm --strict` — valid.
