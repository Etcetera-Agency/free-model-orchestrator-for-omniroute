# web-cookie-candidates Specification

## ADDED Requirements

### Requirement: No automatic discovery

The system SHALL create web-cookie endpoints only from an existing OmniRoute
connection, a static registry, a manual override, or a previously confirmed
model. Automatic model discovery and daily model refresh for web-cookie providers
SHALL NOT occur.

#### Scenario: Web-cookie in daily refresh
- GIVEN a web-cookie provider
- WHEN the daily model refresh runs
- THEN its catalog is not auto-discovered or refreshed

### Requirement: Capability-gated role eligibility

The system SHALL admit a web-cookie endpoint to a role only when the role's
required capabilities are a subset of the endpoint's confirmed capabilities;
roles requiring tool calling, strict JSON, vision, file upload, deterministic
structured extraction, low-latency SLA or high concurrency SHALL exclude
web-cookie endpoints by default. Default capabilities are text only and raised
only after a confirmed probe.

#### Scenario: Tool-calling role
- GIVEN a role requiring tool calling
- WHEN a web-cookie endpoint with text-only confirmed capabilities is considered
- THEN it is excluded from that role

### Requirement: Probe and session health

The system SHALL run only a basic-text probe by default (session valid, HTTP
success, plain-text response, no login/challenge page) and SHALL check session
health daily, marking the endpoint `unavailable` when the session is invalid.

#### Scenario: Expired session
- GIVEN a web-cookie endpoint whose session has expired
- WHEN the daily session-health check runs
- THEN its access status becomes `unavailable`

### Requirement: Fallback-only with limited weight

The system SHALL treat a web-cookie endpoint as fallback-only (not primary
without explicit override) and SHALL NOT count unknown quota as guaranteed
capacity.

#### Scenario: Unknown quota
- GIVEN a web-cookie endpoint with unknown quota
- WHEN allocation runs
- THEN it is added only as opportunistic fallback, never guaranteed capacity
