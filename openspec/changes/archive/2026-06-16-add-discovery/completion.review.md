# Completion Review: add-discovery

Completion of P1: 100%* — candidate filter records zero-cost and standalone free-token reasons without substring false positives.
Completion of P2: 100%* — provider-keyed cost is authoritative; same model can be paid for one provider and free for another.
Completion of P3: 100%* — scanner stores immutable `catalog_hash` snapshots and reports unchanged catalogs.
Completion of P4: 100%* — catalog diff emits provider model events and new endpoint upsert starts discovered/access_pending/not_run.
Completion of P5: 100%* — false-removal guard requires two successful missing snapshots at least five minutes apart and ignores failed fetches.
Completion of P6: 100%* — capacity sums independent confirmed pools once, not connection count.
Completion of P7: 100%* — grouping follows evidence order, falls back shared, and reuses last grouping when rate-limit data is unavailable.
Completion of P8: 100%* — free registry deduplicates `poolKey`, excludes web-cookie models, and does not discover from rankings.
Completion of P9: 100%* — matcher enforces exact-match order, forbidden auto-merge review, confidence auto-use threshold, and provider context precedence.

Code Simplifier:

- Ran simplification pass on touched discovery code.
- Removed unnecessary helper indirection in scanner removal timing.
- Kept grouping/candidate/registry modules small and explicit.

Verification:

- `.venv/bin/python -m pytest tests/test_discovery.py tests/test_foundation.py -q` — 20 passed.
- `/Users/theDay/.nvm/versions/node/v24.1.0/bin/openspec validate add-discovery --strict` — valid.
