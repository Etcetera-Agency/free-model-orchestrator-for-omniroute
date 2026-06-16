# role-scorer Specification

## MODIFIED Requirements

### Requirement: Artificial Analysis scoring v1

The system SHALL fetch Artificial Analysis model benchmark metadata before role
scoring unless an AA snapshot is explicitly injected by tests or offline tooling.
The request SHALL use a configured API key and SHALL fail before network
I/O when the API key is missing. Fetched rows SHALL be normalized into only these
scoring inputs:
`intelligence_index`, `coding_index`, `agentic_index`,
`median_output_tokens_per_second`, and `median_end_to_end_seconds`, normalized to
0..1 via P5/P95 clipped min-max (latency inverted). A missing metric SHALL NOT
be treated as 0 — its weight is redistributed and an uncertainty penalty
applied; if all three quality indices are missing the AA quality score is
unknown.

#### Scenario: Artificial Analysis metadata fetch
- GIVEN role scoring has no injected AA snapshot and an AA API key is configured
- WHEN metadata sync runs before scoring
- THEN the system fetches Artificial Analysis benchmark metadata
- AND sends the key in the `x-api-key` header
- AND stores the index version and normalized metric rows for scoring

#### Scenario: Artificial Analysis API key missing
- GIVEN role scoring has no injected AA snapshot and no AA API key is configured
- WHEN metadata sync prepares the Artificial Analysis request
- THEN it fails with `aa_api_key_required`
- AND no network request is sent

#### Scenario: Artificial Analysis API key redacted
- GIVEN an AA request fails after using a configured API key
- WHEN the error is reported
- THEN the API key and full x-api-key header are not present in the error text

#### Scenario: One missing metric
- GIVEN an endpoint missing `coding_index` only
- WHEN the AA subscore is computed
- THEN the coding weight is redistributed and an uncertainty penalty is added

#### Scenario: Missing metric remains missing
- GIVEN an Artificial Analysis row omits `agentic_index`
- WHEN the row is normalized for scoring
- THEN `agentic_index` remains absent
- AND it is not converted to `0`

### Requirement: Artificial Analysis fetch errors

The system SHALL treat Artificial Analysis fetch failures as metadata sync
failures for new scoring inputs. Missing API key, timeout, network failure,
non-200 status, invalid JSON, missing `intelligence_index_version`, or non-list `data` rows SHALL
produce a structured metadata error. The system SHALL NOT overwrite existing AA
scoring snapshots with invalid or partial payloads. Error output SHALL redact
API keys and x-api-key headers.

#### Scenario: Artificial Analysis non-200
- GIVEN the Artificial Analysis metadata request returns a non-200 status
- WHEN metadata sync runs
- THEN no new AA scoring snapshot is stored
- AND scoring continues only with previously valid data if available

#### Scenario: Artificial Analysis invalid payload
- GIVEN the Artificial Analysis response lacks `intelligence_index_version` or `data` rows
- WHEN metadata sync validates the response
- THEN the response is rejected as invalid
- AND no missing metric is synthesized as zero
