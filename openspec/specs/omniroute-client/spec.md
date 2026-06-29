# omniroute-client Specification

## Purpose
Define the bounded OmniRoute client behavior FMO needs for pool publishing and diagnostics.

## Requirements

### Requirement: OmniRoute client supports publisher calls safely
The client SHALL preserve management auth, request ids, idempotency keys, retry
bounded GET failures, and refuse unsupported pool contract versions.

#### Scenario: 429 with Retry-After
- **WHEN** GET returns 429 with Retry-After
- **THEN** the client waits and retries within the configured bound.

#### Scenario: GET 429 retries exhausted
- **WHEN** GET 429 repeats beyond the bound
- **THEN** the client raises an HTTP error.

#### Scenario: GET transient 5xx retried
- **WHEN** GET returns a transient server failure
- **THEN** the client retries and can succeed.

#### Scenario: GET network error retried
- **WHEN** GET raises a transient network error
- **THEN** the client retries within the configured bound.

#### Scenario: GET non-retriable error
- **WHEN** GET returns a non-retriable status
- **THEN** the client raises without retrying.

#### Scenario: POST carries idempotency key and is not retried
- **WHEN** POST is sent with an idempotency key
- **THEN** the key is sent and POST is not retried.

#### Scenario: POST preserves call-site headers
- **WHEN** call-site headers are passed
- **THEN** they are preserved with management auth headers.

#### Scenario: POST can return non-2xx JSON
- **WHEN** an operator needs the response body for a non-2xx POST
- **THEN** `post_response` preserves status and JSON body.

#### Scenario: POST returns text content for non-JSON success
- **WHEN** POST succeeds with non-JSON text
- **THEN** the client returns status, content and headers.

#### Scenario: Bridge preserves management auth failures
- **WHEN** OmniRoute returns management auth failure
- **THEN** the client surfaces it.

#### Scenario: Invalid Retry-After
- **WHEN** Retry-After is invalid
- **THEN** retry delay is treated as zero.

#### Scenario: Leading slash path
- **WHEN** a path starts with `/`
- **THEN** it stays under the configured base path.

#### Scenario: Supported version publishes
- **WHEN** OmniRoute reports a supported pool contract version
- **THEN** publish is allowed.

#### Scenario: Unsupported contract version refuses publish
- **WHEN** OmniRoute reports an unsupported pool contract version
- **THEN** publish is refused.

#### Scenario: Bridge denies combo test helper
- **WHEN** legacy combo-test helper is requested
- **THEN** the bridge denies it and FMO does not depend on it.
