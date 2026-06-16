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
POST without idempotency protection, and SHALL honor `Retry-After` on `429`. A
`401/403` SHALL fail the run with no apply.

#### Scenario: 429 with Retry-After
- GIVEN a GET returns `429` with a `Retry-After` header
- WHEN the client retries
- THEN it waits at least the indicated interval before retrying

