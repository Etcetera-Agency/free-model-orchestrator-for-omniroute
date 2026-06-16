# Completion Review: add-web-cookie-and-cli

Completion of P1: 100%* — web-cookie endpoints come only from approved sources and are never auto-discovered in daily refresh.
Completion of P2: 100%* — default capabilities are text-only and role eligibility requires confirmed capability subset.
Completion of P3: 100%* — basic-text probe passes plain text, fails login/challenge HTML, and expired sessions become unavailable.
Completion of P4: 100%* — unknown quota is opportunistic only and primary use requires explicit override.
Completion of P5: 100%* — CLI parses per-stage, diagnostics, full/apply/rollback, and aa-index commands with common flags.
Completion of P6: 100%* — exit code mapping includes unsafe apply = 5 with no changes.
Completion of P7: 100%* — dry run returns success without changes and without combo test calls.

Code Simplifier:

- Ran simplification pass on touched web-cookie/CLI code.
- Kept web-cookie policy and CLI parsing/result mapping separate.

Verification:

- `.venv/bin/python -m pytest tests/test_web_cookie_cli.py tests/test_advisory.py tests/test_role_lifecycle.py tests/test_allocation.py tests/test_scoring.py tests/test_quota.py tests/test_discovery.py tests/test_foundation.py -q` — 57 passed.
- `/Users/theDay/.nvm/versions/node/v24.1.0/bin/openspec validate add-web-cookie-and-cli --strict` — valid.
