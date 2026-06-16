# Status: IMPLEMENTED

Web-cookie and CLI implemented with TDD in `tests/test_web_cookie_cli.py`.

- Web-cookie endpoints source only from existing connection, static registry, manual override, or previously confirmed model; no daily auto-discovery.
- Default web-cookie capabilities are text-only; required role capabilities must be confirmed by probe.
- Basic text probe rejects login/challenge pages and session health marks expired sessions unavailable.
- Unknown quota is opportunistic fallback-only; primary requires override.
- CLI exposes stage, diagnostic, apply/rollback/full, and `aa-index` commands with common flags and deterministic exit code mapping.
- Dry run validates locally and never calls `/api/combos/test`.

Verification:

- `.venv/bin/python -m pytest tests/test_web_cookie_cli.py tests/test_advisory.py tests/test_role_lifecycle.py tests/test_allocation.py tests/test_scoring.py tests/test_quota.py tests/test_discovery.py tests/test_foundation.py -q`
- `/Users/theDay/.nvm/versions/node/v24.1.0/bin/openspec validate add-web-cookie-and-cli --strict`
