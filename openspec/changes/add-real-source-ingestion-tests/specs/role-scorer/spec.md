## MODIFIED Requirements

### Requirement: Artificial Analysis scoring v1

The system SHALL fetch Artificial Analysis model benchmark metadata before role
scoring unless an AA snapshot is explicitly injected by tests or offline tooling.
Because Pro-gated `GET /api/v2/language/models` is unavailable to this project,
production ingestion SHALL use the free-tier endpoint
`GET /api/v2/language/models/free`, send the configured API key in the
`x-api-key` header, fail before network I/O when the API key is missing, and
aggregate every page by following the response `pagination` (`has_more` /
`total_pages`) until no further page remains. Fetched `data` rows SHALL be
normalized into only these scoring inputs: `intelligence_index`, `coding_index`,
`agentic_index`, `median_output_tokens_per_second`, and
`median_end_to_end_seconds`, normalized to 0..1 via P5/P95 clipped min-max
(latency inverted). The end-to-end latency input SHALL be read from either
`median_end_to_end_seconds` or the free-endpoint alias
`median_end_to_end_response_time_seconds`. A missing metric SHALL NOT be treated
as 0 — its weight is redistributed and an uncertainty penalty applied; if all
three quality indices are missing the AA quality score is unknown.

#### Scenario: Artificial Analysis metadata fetch
- GIVEN role scoring has no injected AA snapshot and an AA API key is configured
- WHEN metadata sync runs before scoring
- THEN the system fetches `GET /api/v2/language/models/free` benchmark metadata
- AND sends the key in the `x-api-key` header
- AND stores the index version and normalized metric rows for scoring

#### Scenario: Artificial Analysis free-tier pagination
- GIVEN the free-tier response reports more than one page via `pagination`
- WHEN the snapshot is fetched
- THEN every page is requested in turn following `has_more`
- AND the normalized rows from all pages are combined into one snapshot

#### Scenario: Artificial Analysis API key missing
- GIVEN role scoring has no injected AA snapshot and no AA API key is configured
- WHEN metadata sync prepares the Artificial Analysis request
- THEN it fails with `aa_api_key_required`
- AND no network request is sent

#### Scenario: Artificial Analysis API key redacted
- GIVEN an AA request fails after using a configured API key
- WHEN the error is reported
- THEN the API key and full `x-api-key` header are not present in the error text

#### Scenario: End-to-end latency alias
- GIVEN a free-tier row exposes `median_end_to_end_response_time_seconds` and no `median_end_to_end_seconds`
- WHEN the row is normalized for scoring
- THEN the value is recorded as the `median_end_to_end_seconds` metric

#### Scenario: Missing metric remains missing
- GIVEN an Artificial Analysis row omits `agentic_index`
- WHEN the row is normalized for scoring
- THEN `agentic_index` remains absent
- AND it is not converted to `0`
