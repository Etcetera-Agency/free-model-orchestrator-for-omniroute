# omniroute-client Specification

## MODIFIED Requirements

### Requirement: Retry policy

The system SHALL retry only idempotent GET requests, SHALL NOT retry an apply
POST without idempotency protection, and SHALL honor valid positive
`Retry-After` values on `429`. Invalid, empty, nonnumeric or negative
`Retry-After` values SHALL be treated as `0.0`. GET retry exhaustion, non-429
4xx, and 5xx responses SHALL fail with `RuntimeError`. A `401/403` SHALL fail
the run with no apply.

#### Scenario: 429 with Retry-After
- GIVEN a GET returns `429` with a valid positive `Retry-After` header
- WHEN the client retries
- THEN it waits at least the indicated interval before retrying

#### Scenario: GET 429 retries exhausted
- GIVEN a GET keeps returning `429`
- WHEN all retry attempts are consumed
- THEN the client raises `RuntimeError`

#### Scenario: GET non-retriable error
- GIVEN a GET returns `500` or a non-429 `4xx`
- WHEN the client handles the response
- THEN it raises `RuntimeError` without retrying

#### Scenario: Invalid Retry-After
- GIVEN a `Retry-After` header is empty, nonnumeric, invalid or negative
- WHEN the delay is parsed
- THEN the parsed delay is `0.0`

### Requirement: Safe URL construction

The system SHALL join OmniRoute base URLs and request paths without allowing a
leading slash in the path to replace the base path.

#### Scenario: Leading slash path
- GIVEN the base URL has no trailing slash and the request path starts with `/`
- WHEN the request URL is built
- THEN the URL remains under the configured OmniRoute base URL
