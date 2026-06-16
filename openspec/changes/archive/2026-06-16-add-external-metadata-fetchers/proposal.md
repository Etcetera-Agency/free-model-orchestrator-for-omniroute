# add-external-metadata-fetchers

## Why

The current code parses models.dev-like payloads and Artificial Analysis-like
metrics after they are already in memory, but it does not own the network sync
step for either source.

That leaves two holes in the daily pipeline:

- `https://models.dev/api.json` is named in specs and docs, but no function
  fetches it, validates HTTP status, parses JSON, or passes it into candidate
  discovery.
- Artificial Analysis scores are used by scoring, quality gates, latency
  fallback, and index migration, but no request layer fetches or normalizes AA
  data before those modules run.

Without explicit fetchers, CLI/scheduler commands cannot run the full pipeline
from external metadata sources, and tests can only exercise hand-built payloads.

## What Changes

- Add a models.dev catalog fetch requirement for `https://models.dev/api.json`.
- Add deterministic error behavior for non-200, timeout/network failure, invalid
  JSON, and invalid top-level payload shape.
- Add an Artificial Analysis sync requirement that fetches benchmark/index data
  from `https://artificialanalysis.ai/api/v2/language/models`, authenticates
  with a configured API key in the `x-api-key` header, normalizes `data` rows
  into scoring metrics, and exposes the fetched intelligence index version for
  migration detection.
- Add scheduler/CLI requirements so daily sync commands call both fetchers before
  candidate discovery, matching, scoring, and AA index migration.
- Keep fetchers testable through injected HTTP clients/transports. Unit tests
  SHALL use fake clients, not live external HTTP.

## Pseudocode

```text
def fetch_models_dev_catalog(http_client, url="https://models.dev/api.json"):
  response = http_client.get(url, timeout=timeout)
  if response.status_code != 200:
    raise ExternalMetadataError("models_dev_http_error")
  payload = response.json()
  if not isinstance(payload, dict) or "providers" not in payload:
    raise ValueError("models_dev_payload_invalid")
  return payload

def sync_models_dev_candidates(http_client):
  catalog = fetch_models_dev_catalog(http_client)
  return build_free_candidates(catalog)

def fetch_artificial_analysis_index(http_client, url, api_key):
  if not api_key:
    raise ValueError("aa_api_key_required")
  response = http_client.get(
    url,
    headers={"x-api-key": api_key},
    timeout=timeout,
  )
  if response.status_code != 200:
    raise ExternalMetadataError("aa_http_error")
  payload = response.json()
  validate payload contains intelligence_index_version and data rows
  return normalize data rows:
    slug as model_id
    intelligence_index
    coding_index
    agentic_index
    median_output_tokens_per_second
    median_end_to_end_seconds
    intelligence_index_version
  never log API key or x-api-key header

def daily_metadata_sync():
  models_dev_catalog = fetch_models_dev_catalog(...)
  candidates = build_free_candidates(models_dev_catalog)
  aa_snapshot = fetch_artificial_analysis_index(...)
  if aa_snapshot.index_version != active_version:
    detect_index_change(...)
  continue matching/scoring with fetched metadata
```

## Impact

- Specs modified:
  - `free-candidate-discovery`
  - `role-scorer`
  - `aa-index-migration`
  - `scheduler`
  - `cli-and-operations`
- Code impact expected:
  - new or extended metadata client module, likely `src/fmo/models_dev.py` and
    `src/fmo/artificial_analysis.py`;
  - CLI/scheduler wiring;
  - deterministic tests with fake HTTP clients.
- External behavior:
  - daily/full sync can start from real external metadata URLs;
  - failures are explicit and conservative;
  - no live external calls are required in unit tests.
