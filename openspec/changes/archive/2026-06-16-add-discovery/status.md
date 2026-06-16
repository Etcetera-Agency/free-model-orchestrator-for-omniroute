# Status: IMPLEMENTED

Discovery implemented with TDD in `tests/test_discovery.py`.

- models.dev candidate selection reads provider-keyed cost and standalone `free` tokens.
- Provider scanner stores content-hashed snapshots, skips unchanged diffs, emits add/remove events, and upserts new endpoints in safe initial states.
- False-removal guard requires two successful fetches at least five minutes apart.
- Account grouping uses conservative shared fallback and reuses last grouping when rate limits are unavailable.
- Free registry sync deduplicates `poolKey`, ignores rankings for discovery, and excludes web-cookie models.
- Matcher applies ordered exact matching, confidence gates, forbidden variant review, and provider context override.

Verification:

- `.venv/bin/python -m pytest tests/test_discovery.py tests/test_foundation.py -q`
- `openspec validate add-discovery --strict`
