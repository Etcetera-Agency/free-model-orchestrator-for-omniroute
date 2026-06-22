# Implementation Tasks

## 1. TDD Coverage

- [x] 1.1 Add a sequence-returning fake HTTP client to `tests/test_discovery.py`
  (a list of responses/exceptions consumed per `get` call) plus a recording
  `sleep` seam, so retry attempts and backoff waits are asserted without real
  sleeping.
- [x] 1.2 Failing test: first `get` raises a transport error, second returns a
  valid `200` provider-keyed body → `fetch_models_dev_catalog` returns the
  second-attempt catalog and raises nothing.
  Bind `@pytest.mark.spec("free-candidate-discovery::Transient network error then success")`.
- [x] 1.3 Failing test: first attempt `503`, second attempt valid `200` → catalog
  from the second attempt.
  Bind `@pytest.mark.spec("free-candidate-discovery::Transient 503 then success")`.
- [x] 1.4 Failing test: first attempt `429` with a parseable `Retry-After`, next
  attempt valid `200` → fetcher waits the bounded hint (assert via the `sleep`
  seam) and returns the catalog.
  Bind `@pytest.mark.spec("free-candidate-discovery::429 honours Retry-After then succeeds")`.
- [x] 1.5 Failing test: every attempt up to the cap returns `503` → exactly
  `attempts` calls made, a single `ExternalMetadataError("models_dev",
  "http_error", 503)` raised, no candidates.
  Bind `@pytest.mark.spec("free-candidate-discovery::Transient failures exhaust the attempt cap")`.
- [x] 1.6 Failing test: first attempt `404` → no retry, single request, HTTP
  error raised.
  Bind `@pytest.mark.spec("free-candidate-discovery::Non-transient status is not retried")`.
- [x] 1.7 Failing test: first attempt `200` with JSON that fails to parse → no
  retry, single request, invalid JSON error.
  Bind `@pytest.mark.spec("free-candidate-discovery::Invalid JSON is not retried")`.
- [x] 1.8 Keep the existing `models.dev fetch errors` scenarios green: a single
  non-200 (e.g. `404`), the real top-level body, and the invalid-payload body
  still behave as before.
- [x] 1.9 Stage every new scenario id in `tests/spec_coverage_pending.txt` until
  its test lands; remove each line as the matching test is added.

## 2. Implementation

- [x] 2.1 Add a module constant for the attempt cap (default `3`) and a transient
  status set `{502, 503, 504}` in `src/fmo/models_dev.py`; treat `429` as a
  distinct transient class that consults `Retry-After`.
- [x] 2.2 Wrap the single `http_client.get` in a bounded attempt loop: on a
  transport exception or a transient status, back off and retry while attempts
  remain; on the final attempt, raise the same structured error as today.
- [x] 2.3 Add an injectable `sleep` parameter (default `time.sleep`) and a bounded
  exponential backoff; for `429`, prefer a bounded `Retry-After` parse (reuse the
  approach in `src/fmo/omniroute.py::_retry_after_seconds`, copying or factoring a
  small helper — do not import private bridge state).
- [x] 2.4 Leave non-transient handling untouched: other non-200 → `http_error` on
  first response; JSON parse failure → `invalid_json`; non-provider-keyed payload
  → `invalid_payload`. None of these retry.
- [x] 2.5 Keep `fetch_models_dev_catalog`/`sync_models_dev_candidates` signatures
  backward compatible (new params keyword-only with defaults); the success path,
  URL, and `timeout` forwarding are unchanged.

## 3. Verification

- [x] 3.1 Run targeted tests: `.venv/bin/python -m pytest tests/test_discovery.py -q`.
- [x] 3.2 Run the full suite: `.venv/bin/python -m pytest -q` (includes the
  executable-spec coverage gate).
- [x] 3.3 `npx --yes @fission-ai/openspec@latest validate add-models-dev-fetch-retry --strict`.
  Local OpenSpec binary was used after `npx` failed on network DNS; strict
  change validate and strict validate-all passed.
- [x] 3.4 Run Code Simplifier over the touched code before finishing.
- [x] 3.5 Update `completion.review`, shrink `tests/spec_coverage_pending.txt`
  and `EXPECTED_ACTIVE_PENDING` in `tests/test_runtime_documentation.py` to empty
  for this slice, and drop the slice entry from `openspec/TODO.md` once every
  scenario test has landed.
