# free-candidate-discovery Specification

## Purpose
TBD - created by archiving change add-discovery. Update Purpose after archive.
## Requirements
### Requirement: Candidate selection rule

The system SHALL fetch the models.dev provider-keyed catalog from
`https://models.dev/api.json` before building free candidates unless a catalog
payload is explicitly injected by tests or offline tooling. The system SHALL
mark a model as a free candidate when any of these hold, read from the
provider→model level of models.dev: listed input cost = 0 AND listed output cost
= 0; OR the normalized model id contains the standalone token `free`; OR the
normalized display name contains the standalone word `free`. The system SHALL
NOT use naive substring matching that catches `free` inside other words.

#### Scenario: Fetch models.dev api catalog
- GIVEN no models.dev catalog payload is injected
- WHEN metadata sync starts free candidate discovery
- THEN the system requests `GET https://models.dev/api.json`
- AND the parsed JSON object is passed to candidate discovery

#### Scenario: Zero-cost provider offering
- GIVEN a models.dev provider offering with `cost.input = 0` and `cost.output = 0`
- WHEN the candidate filter runs
- THEN the model is recorded as a candidate with reason `zero_cost`

#### Scenario: Free token in model id
- GIVEN a model id containing the standalone token `free`
- WHEN the candidate filter runs
- THEN the model is recorded with reason `free_in_model_id`

#### Scenario: Missing cost is not free
- GIVEN a model with no `cost` field
- WHEN the candidate filter runs
- THEN the model is NOT recorded as zero-cost solely due to the missing field

#### Scenario: False free token
- GIVEN a model id contains `freedom`, `carefree`, or `freebsd`
- WHEN candidate detection runs
- THEN it is not treated as a free token signal

#### Scenario: Cost is not an object
- GIVEN cost metadata is not a dict/object
- WHEN candidate detection runs
- THEN it is not treated as zero cost

#### Scenario: Only input cost is zero
- GIVEN input cost is zero but output cost is not zero
- WHEN candidate detection runs
- THEN it is not treated as zero cost

#### Scenario: Multiple signals collapse
- GIVEN two or more candidate signals are present
- WHEN candidate evidence is recorded
- THEN the signal is collapsed to `multiple_signals`

### Requirement: Cost is read per provider

The system SHALL read pricing from the provider-keyed models.dev data, because
the same model id may be paid under one provider and free under another. The flat
top-level `models` map (which carries no `cost`) SHALL NOT be used for cost.

#### Scenario: Same model differs by provider
- GIVEN model id `X` priced above zero under provider A and zero under provider B
- WHEN candidates are built
- THEN only the provider-B endpoint is recorded as a zero-cost candidate

### Requirement: Candidate is a lead, not proof

The system SHALL treat name/id matches as candidates only; the final free
decision is made per OmniRoute provider/account by access classification and
quota research.

#### Scenario: Name match stays unconfirmed
- GIVEN a model whose name contains `free` but has no confirmed quota
- WHEN the candidate enters classification
- THEN it is not activated until free access is confirmed

### Requirement: models.dev fetch errors

The system SHALL fail metadata sync conservatively when the models.dev catalog
cannot be fetched or parsed. A transient failure (transport/network error or HTTP
`502/503/504/429`) SHALL first be retried under the bounded retry policy; only
after the attempt cap is exhausted does it produce a structured metadata error. A
non-transient failure — any other non-200 status, invalid JSON, or a payload that
is not a provider-keyed object — SHALL produce a structured metadata error on the
first response with no retry. In all cases the failure SHALL NOT create or update
free candidates from partial data. The real `https://models.dev/api.json` body is
a top-level object keyed by provider id (`{"<provider>": {"models": {...}}}`) with
no `providers` wrapper; the fetcher SHALL accept that shape and SHALL also accept
an explicitly injected `{"providers": {...}}` payload, normalizing both into the
canonical provider-keyed form before candidate discovery. A payload that carries
no provider-like object (for example an error body such as `{"error": ...}`) SHALL
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

### Requirement: models.dev fetch retries transient failures

The system SHALL retry a transient models.dev catalog fetch failure with bounded
exponential backoff, up to 3 attempts total (the initial request plus up to two
retries), before surfacing a metadata error. A transient failure is a
transport/network exception raised by the HTTP client, or an HTTP `502`, `503`,
`504`, or `429` response. A `429` carrying a parseable `Retry-After` SHALL wait
that bounded hint instead of the backoff default. The attempt cap and the
backoff sleep SHALL be bounded and injectable so the retry is deterministic and
fast under test. The success path, request URL, and `timeout` argument are
unchanged: when a retry succeeds, the returned catalog is identical to a
first-attempt success.

#### Scenario: Transient network error then success
- GIVEN the first `GET https://models.dev/api.json` raises a transport error
- AND the second attempt returns a valid provider-keyed `200` body
- WHEN metadata sync runs
- THEN the fetcher retries and returns the catalog from the second attempt
- AND no metadata error is raised

#### Scenario: Transient 503 then success
- GIVEN the first attempt returns HTTP `503`
- AND the second attempt returns a valid provider-keyed `200` body
- WHEN the catalog is fetched
- THEN the fetcher retries and returns the second-attempt catalog

#### Scenario: 429 honours Retry-After then succeeds
- GIVEN the first attempt returns HTTP `429` with a parseable `Retry-After`
- AND the next attempt returns a valid `200` body
- WHEN the catalog is fetched
- THEN the fetcher waits the bounded `Retry-After` hint and returns the catalog

#### Scenario: Transient failures exhaust the attempt cap
- GIVEN every attempt up to the cap returns HTTP `503`
- WHEN metadata sync runs
- THEN the fetcher stops at the attempt cap
- AND a single models.dev HTTP error is raised with the final status
- AND candidate discovery is skipped with no candidates created

#### Scenario: Non-transient status is not retried
- GIVEN the first attempt returns HTTP `404`
- WHEN the catalog is fetched
- THEN the fetcher does not retry
- AND a models.dev HTTP error is raised after a single request

#### Scenario: Invalid JSON is not retried
- GIVEN the first attempt returns `200` with a body that fails JSON parsing
- WHEN the catalog is fetched
- THEN the fetcher does not retry
- AND an invalid JSON error is raised after a single request
