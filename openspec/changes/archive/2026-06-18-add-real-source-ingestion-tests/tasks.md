## 1. models.dev real catalog shape

- [x] 1.1 Failing test: real top-level provider-keyed `api.json` body (from the
  recorded fixture) is accepted and yields zero-cost candidates.
- [x] 1.2 Failing test: a non-provider-keyed object (error body) still fails as
  `invalid_payload`; an injected `{"providers": ...}` payload still works.
- [x] 1.3 Normalize the top-level provider-keyed payload into the canonical
  `{"providers": ...}` form inside `fetch_models_dev_catalog`.

## 2. Artificial Analysis free-tier pagination

- [x] 2.1 Failing test: `fetch_artificial_analysis_free_snapshot` requests
  `GET /api/v2/language/models/free`, follows pagination, and concatenates rows.
- [x] 2.2 Failing test: `median_end_to_end_response_time_seconds` is normalized to
  the canonical `median_end_to_end_seconds` metric.
- [x] 2.3 Implement the paginated free reader and the metric alias.

## 3. OmniRoute fixture-backed ingestion

- [x] 3.1 `tests/_fixtures.py` loader for `reference/fixtures/external-responses`.
- [x] 3.2 Replay `/api/free-models`, `/api/providers`, `/api/rate-limits`,
  `/api/free-provider-rankings` through `OmniRouteClient` + registry/scanner/
  account parsers, asserting real shapes.

## 4. Live source checks

- [x] 4.1 Live AA free-tier ingestion test using `Secrets/AA.txt`, skipped when
  the key or network is unavailable.
- [x] 4.2 Live models.dev `api.json` ingestion test, skipped when the network is
  unavailable.

## 5. Validation

- [x] 5.1 `.venv/bin/python -m pytest -q` green.
- [x] 5.2 `openspec validate add-real-source-ingestion-tests --strict` passes.
