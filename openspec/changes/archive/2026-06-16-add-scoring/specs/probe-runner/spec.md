# probe-runner Specification

## ADDED Requirements

### Requirement: Probe only after free confirmation

The system SHALL probe an endpoint only when the access classifier returned
`free_unlimited`, `free_quota_available` or `free_promotional_available` and the
quota manager reserved probe capacity. Probing SHALL NOT be used to test whether
money is charged.

#### Scenario: Unconfirmed endpoint
- GIVEN an endpoint classified `unknown_excluded`
- WHEN the probe runner is invoked
- THEN it does not probe the endpoint

### Requirement: Isolated probe request

The system SHALL probe via the dedicated `POST /v1/providers/{provider}/chat/completions`
route with an explicit model and `X-OmniRoute-No-Cache: true`, so probing cannot
be routed to another provider. Only test prompts are stored, never user content.

#### Scenario: Probe routing
- GIVEN a probe for provider P, model M
- WHEN the probe executes
- THEN it targets P's dedicated route with M explicitly, not generic routing

### Requirement: Capability-gated suites

The system SHALL run the basic-text suite for every new endpoint and run
structured-output, tool-calling, vision and long-context suites only when that
capability is claimed and quota reserve allows.

#### Scenario: Unclaimed capability
- GIVEN an endpoint that does not claim tool calling
- WHEN probing runs
- THEN the tool-calling suite is skipped

### Requirement: Probe error handling and promotion

The system SHALL handle probe errors as: one retry on network/5xx; no retry on
429 (hand to quota manager); auth-degraded on 401/403; immediate exclusion plus
quota research on 402; catalog-stale on invalid model. An endpoint becomes
`active` only if the basic probe passed, free access is still valid, the breaker
is closed, and match confidence is sufficient.

#### Scenario: Paid charge during probe
- GIVEN a probe returns 402
- WHEN the error is handled
- THEN the endpoint is excluded immediately and quota research is triggered
