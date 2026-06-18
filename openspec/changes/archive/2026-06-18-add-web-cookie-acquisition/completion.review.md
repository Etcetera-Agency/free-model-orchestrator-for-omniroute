# Completion Review: add-web-cookie-acquisition

## Code Simplifier

- Reused the shared probe classifier inside `web_cookie_text_probe` and made
  expired-session detection handle both session markers and response body text.

## Verification

- `tests/test_web_cookie_cli.py` and `tests/test_web_cookie_acquisition.py` -> 16 passed.
- `.venv/bin/python -m pytest -q` -> 191 passed, 7 skipped.
- `openspec validate add-web-cookie-acquisition --strict` -> valid.
