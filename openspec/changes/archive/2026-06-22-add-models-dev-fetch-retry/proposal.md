# Change: models.dev fetch retries bounded transient failures

## Why

The models.dev catalog fetch makes exactly one HTTP request and gives up on the
first failure:

- `fetch_models_dev_catalog`
  ([src/fmo/models_dev.py](../../../src/fmo/models_dev.py)) does a single
  `http_client.get(url, timeout=timeout)`; any transport exception becomes
  `ExternalMetadataError("models_dev", "network_error")` and any non-200 becomes
  `("models_dev", "http_error", status)`. There is no second attempt.

The orchestrator runs **once per day**, so the next opportunity to refetch is
~24h away. `https://models.dev/api.json` is a public endpoint behind a CDN, where
single transient failures — TLS/connect timeouts and momentary `502/503/504` —
are normal and almost always succeed on an immediate retry. With no retry, one
such blip fails the early `external-metadata-sync` stage with
`external_dependency_failed` and starves the whole daily run of fresh model
metadata, degrading matching and scoring for a full day.

This is the only fetch site that lacks retry. The OmniRoute client already
retries transient GETs (`502/503/504`) and `429` with `Retry-After`
([src/fmo/omniroute.py](../../../src/fmo/omniroute.py) `_is_transient_get_status`,
`_retry_after_seconds`). That bounded-retry pattern simply was never applied to
the external metadata fetch.

Scope is deliberately narrow: **only** bounded retry of transient failures. No
caching and no ETag/conditional requests — those are pointless for a once-a-day
run with nothing to reuse between days, and remain explicitly out of scope per
`openspec/TODO.md`.

## What Changes

- `fetch_models_dev_catalog` SHALL retry a **transient** failure with bounded
  exponential backoff, up to **3 attempts total** (the initial request plus up to
  two retries) before surfacing an error. This mirrors the OmniRoute client's
  existing bounded-retry semantics where the attempt count is the total tries.
- Transient failures are: a transport/network exception raised by the HTTP
  client, and HTTP status `502`, `503`, `504`, or `429`. A `429` with a parseable
  `Retry-After` SHALL wait that hint (bounded) instead of the backoff default.
- Non-transient failures SHALL fail conservatively on the first response, with no
  retry, exactly as today: any other non-200 status (e.g. `400/401/403/404/500`),
  invalid JSON, and a non-provider-keyed/invalid payload.
- When retries are exhausted, behaviour is unchanged: a single structured
  `ExternalMetadataError` is raised (the last transient class — `network_error`
  or `http_error` with the final status), candidate discovery is skipped, and no
  candidates are created from partial data.
- Backoff and attempt count SHALL be bounded and injectable (a `sleep` seam and
  an attempts cap) so tests stay fast and deterministic; the default attempts cap
  is a module constant. No real wall-clock sleeping in tests.
- The success path, request URL, `timeout` argument, normalization of both the
  real top-level provider-keyed body and the injected `{"providers": {...}}`
  shape, and all existing error reasons are unchanged.

## Impact

- Affected specs: `free-candidate-discovery` (the "models.dev fetch errors"
  requirement is refined to "after bounded retries"; a new retry requirement is
  added).
- Affected code: `src/fmo/models_dev.py` (`fetch_models_dev_catalog` retry loop,
  transient classification, backoff/`Retry-After` seam), `tests/test_discovery.py`
  (a sequence-returning fake HTTP client).
- No change to `external-metadata-sync` stage wiring, candidate-building logic,
  persistence, or the Artificial Analysis fetch path (out of scope here).
- No new dependency. Backoff reuses the same approach already in the OmniRoute
  client.
