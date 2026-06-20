# omniroute-client Specification

## Purpose
TBD - created by archiving change add-foundation. Update Purpose after archive.
## Requirements
### Requirement: Single OmniRoute client

The system SHALL route every OmniRoute call through one client; no other module
calls OmniRoute directly. The client SHALL add auth, set connect/read timeouts,
generate an `X-Request-Id`, log method/path/status/duration, and store sanitized
responses (never secrets, bearer tokens or cookies).

#### Scenario: Module needs OmniRoute data
- GIVEN any module needs provider, quota or telemetry data
- WHEN it makes the call
- THEN the call goes through the shared OmniRoute client, not a direct request

### Requirement: Version handshake gates writes

The system SHALL fetch the OmniRoute version at startup and check the
compatibility matrix. If the version is unknown, the client SHALL allow read-only
calls and forbid apply.

#### Scenario: Unknown OmniRoute version
- GIVEN the running OmniRoute version is not in the compatibility matrix
- WHEN the orchestrator runs
- THEN read-only calls are allowed and any apply is refused

### Requirement: Retry policy

The system SHALL retry only idempotent GET requests, SHALL NOT retry an apply
POST without idempotency protection, and SHALL honor valid positive
`Retry-After` values on `429`. Invalid, empty, nonnumeric or negative
`Retry-After` values SHALL be treated as `0.0`. GET requests SHALL additionally
retry transient server and network failures — HTTP `502`, `503`, `504`, and
connection/timeout exceptions — bounded by `max_get_retries` with backoff and a
total retry budget so a degraded upstream cannot stall the run. GET retry
exhaustion, non-429/non-transient `4xx`, and non-transient `5xx` responses SHALL
fail with `RuntimeError`. A `401/403` SHALL fail the run with no apply. When the
caller supplies an idempotency key the client SHALL send it as an
`Idempotency-Key` header on the POST while keeping a per-attempt `X-Request-Id`;
POST SHALL remain non-retriable.

#### Scenario: 429 with Retry-After
- GIVEN a GET returns `429` with a valid positive `Retry-After` header
- WHEN the client retries
- THEN it waits at least the indicated interval before retrying

#### Scenario: GET 429 retries exhausted
- GIVEN a GET keeps returning `429`
- WHEN all retry attempts are consumed
- THEN the client raises `RuntimeError`

#### Scenario: GET transient 5xx retried
- GIVEN a GET returns `503` then `200`
- WHEN the client handles the responses within `max_get_retries`
- THEN it retries and returns the successful body

#### Scenario: GET network error retried
- GIVEN a GET raises a connection/timeout error then succeeds
- WHEN the client handles the failure within `max_get_retries`
- THEN it retries and returns the successful body
- AND exhausting the transient retries raises `RuntimeError`

#### Scenario: GET non-retriable error
- GIVEN a GET returns a non-429 `4xx` or a non-transient `5xx`
- WHEN the client handles the response
- THEN it raises `RuntimeError` without retrying

#### Scenario: Invalid Retry-After
- GIVEN a `Retry-After` header is empty, nonnumeric, invalid or negative
- WHEN the delay is parsed
- THEN the parsed delay is `0.0`

#### Scenario: POST carries idempotency key and is not retried
- GIVEN a POST is issued with a supplied idempotency key
- WHEN the request is sent
- THEN it carries an `Idempotency-Key` header and a per-attempt `X-Request-Id`
- AND the POST is not retried

### Requirement: Safe URL construction

The system SHALL join OmniRoute base URLs and request paths without allowing a
leading slash in the path to replace the base path.

#### Scenario: Leading slash path
- GIVEN the base URL has no trailing slash and the request path starts with `/`
- WHEN the request URL is built
- THEN the URL remains under the configured OmniRoute base URL

