# Change: Ingest real models.dev and Artificial Analysis shapes, fixture-back OmniRoute

## Why

The TODO defers replacing hand-built payloads with realistic recordings and
hardening the external-source boundaries. Two recorded/live shapes do not match
the current parsers:

- Real `https://models.dev/api.json` is a **top-level provider-keyed object**
  (`{"<provider>": {...}}`), but `fetch_models_dev_catalog` only accepts a
  `{"providers": {...}}` wrapper, so it rejects the real catalog (and its own
  recorded fixture) as `invalid_payload`.
- The Pro `GET /api/v2/language/models` endpoint returns `403` without Pro
  access. The usable source is the paginated free-tier endpoint
  `GET /api/v2/language/models/free` (`x-api-key`), whose rows expose
  `median_end_to_end_response_time_seconds` rather than the canonical
  `median_end_to_end_seconds`.

## What Changes

- models.dev fetcher accepts the real top-level provider-keyed catalog as well
  as an explicitly injected `{"providers": ...}` payload; non-provider-keyed
  objects (e.g. error bodies) still fail as `invalid_payload`.
- Artificial Analysis fetcher gains a free-tier paginated reader
  (`/api/v2/language/models/free`) that aggregates every page following the
  `pagination`/`has_more` signal, and the metric normalizer accepts the
  `median_end_to_end_response_time_seconds` alias.
- Test slices replace hand-built payloads at these boundaries:
  - OmniRoute management responses are replayed from
    `reference/fixtures/external-responses/*` through `OmniRouteClient` and the
    registry/scanner/account parsers.
  - models.dev and Artificial Analysis ingestion are exercised against the
    **live** endpoints (AA key read from `Secrets/AA.txt`), skipping cleanly when
    the network or key is unavailable, while keeping the deterministic suite
    fixture-backed.

(Hermes inventory real-shape ingestion is split out into the separate change
`add-hermes-inventory-real-shapes`.)

## Impact

- Affected specs: `free-candidate-discovery`, `role-scorer`
- Affected code: `src/fmo/models_dev.py`, `src/fmo/artificial_analysis.py`
- New tests: `tests/_fixtures.py`, `tests/test_omniroute_fixture_ingestion.py`,
  `tests/test_live_external_sources.py`, additions to
  `tests/test_discovery.py` and `tests/test_external_metadata.py`
