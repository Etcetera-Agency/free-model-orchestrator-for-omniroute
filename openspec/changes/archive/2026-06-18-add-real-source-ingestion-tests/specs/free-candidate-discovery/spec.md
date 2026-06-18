## MODIFIED Requirements

### Requirement: models.dev fetch errors

The system SHALL fail metadata sync conservatively when the models.dev catalog
cannot be fetched or parsed. Timeout, network failure, non-200 status, invalid
JSON, or a payload that is not a provider-keyed object SHALL produce a structured
metadata error and SHALL NOT create or update free candidates from partial data.
The real `https://models.dev/api.json` body is a top-level object keyed by
provider id (`{"<provider>": {"models": {...}}}`) with no `providers` wrapper;
the fetcher SHALL accept that shape and SHALL also accept an explicitly injected
`{"providers": {...}}` payload, normalizing both into the canonical
provider-keyed form before candidate discovery. A payload that carries no
provider-like object (for example an error body such as `{"error": ...}`) SHALL
be rejected as an invalid payload.

#### Scenario: models.dev non-200
- GIVEN `GET https://models.dev/api.json` returns a non-200 status
- WHEN metadata sync runs
- THEN candidate discovery is skipped
- AND the sync result records a models.dev HTTP error

#### Scenario: models.dev real top-level provider-keyed body
- GIVEN models.dev returns a top-level object keyed by provider id with no `providers` wrapper
- WHEN metadata sync parses the response
- THEN the body is treated as the provider map
- AND zero-cost provider offerings are recorded as candidates

#### Scenario: models.dev invalid payload
- GIVEN models.dev returns invalid JSON or a JSON object that contains no provider-like object
- WHEN metadata sync parses the response
- THEN the sync fails with an invalid payload error
- AND no candidates are produced from that response
