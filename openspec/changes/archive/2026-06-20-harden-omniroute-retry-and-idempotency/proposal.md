# harden-omniroute-retry-and-idempotency

## Why

`OmniRouteClient._request` (`src/fmo/omniroute.py`) retries only `GET` on `429`:

```python
if response.status_code == 429 and method == "GET" and attempt + 1 < attempts:
    self.sleep(_retry_after_seconds(response.headers.get("Retry-After")))
    continue
```

Two robustness gaps for a service that runs as a daily batch against an upstream
gateway:

1. **No retry on transient 5xx / network errors for GET.** A single `502/503`
   or a connection blip on any read stage (catalog scan, telemetry, quota sync,
   registry) immediately fails the whole stage with `RuntimeError` →
   `external_dependency_failed` (exit 4), aborting the daily run. The current
   `Retry policy` requirement explicitly makes 5xx non-retriable, which is safe
   for writes but needlessly fragile for idempotent reads.
2. **No idempotency key on POST.** The repo has a stage-level idempotency module,
   but the HTTP client sends only `X-Request-Id` (a fresh UUID per attempt). The
   `Retry policy` requirement already says an apply POST must not be retried
   "without idempotency protection" — there is currently no such protection
   header to enable safe at-most-once apply if retry were ever added.

This slice does **not** add POST retries (apply stays at-most-once); it adds
bounded GET retry on transient server/network errors and an optional
idempotency-key header so the existing no-retry-POST guarantee is explicit and
upgradable.

## What Changes

- Extend GET retry to transient failures: `502/503/504` and connection/timeout
  exceptions, bounded by `max_get_retries`, with backoff; non-transient `4xx`
  (and `5xx` beyond the transient set) still fail fast. `429` handling is
  unchanged.
- Keep POST non-retriable.
- Send an `Idempotency-Key` header on POST when the caller supplies one (e.g. the
  apply stage's per-combo idempotency key), so a future safe-retry is possible
  and replays are deduplicated upstream; `X-Request-Id` stays per-attempt.
- Bound total retry time/attempts so a degraded upstream cannot stall the daily
  run indefinitely.

## Impact

- Modified spec: `omniroute-client` (Retry policy — transient GET retry +
  idempotency-key on POST).
- Affected code: `src/fmo/omniroute.py` (`_request`, `_headers`, retry classify),
  apply-stage call site to pass the idempotency key.
- Confirm against `../OmniRoute` whether the management API honors an
  `Idempotency-Key` header; if not, ship the header as forward-compatible and
  keep the at-most-once POST guarantee as the safety net.
- Risk: low; reads become more resilient, write semantics unchanged.
