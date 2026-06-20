# Implementation Tasks (TDD)

Write each test first (red) → green → refactor. Use an injected fake transport to
simulate status sequences and exceptions; no live network. Confirm header/route
shapes against `../OmniRoute`.

## Tasks

- [x] 1. TEST: a GET returning `503` then `200` succeeds within `max_get_retries`
  with backoff → implement transient 5xx (`502/503/504`) GET retry.
- [x] 2. TEST: a GET raising a connection/timeout error then succeeding is
  retried; exhausted transient retries raise `RuntimeError` → implement
  network-exception retry with bound.
- [x] 3. TEST: a non-transient `4xx` (and `5xx` outside the transient set) still
  fails fast without retry → preserve fail-fast classification.
- [x] 4. TEST: `429` Retry-After handling is unchanged (valid/invalid/negative →
  `0.0`) → regression guard.
- [x] 5. TEST: POST is never retried; when an idempotency key is supplied the
  request carries an `Idempotency-Key` header and `X-Request-Id` is still
  per-attempt → implement header passthrough.
- [x] 6. TEST: total retry budget is bounded so a persistently degraded upstream
  cannot stall the run → implement attempt/time bound.
- [x] 7. Bind tests with `@pytest.mark.spec("omniroute-client::...")`, drop
  matching lines from `tests/spec_coverage_pending.txt`, run full `pytest` and
  `openspec validate harden-omniroute-retry-and-idempotency --strict`.
