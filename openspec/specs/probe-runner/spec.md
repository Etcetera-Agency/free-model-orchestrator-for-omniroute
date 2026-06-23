# probe-runner Specification

## Purpose
TBD - created by archiving change add-scoring. Update Purpose after archive.
## Requirements
### Requirement: Probe only after free confirmation

The system SHALL probe only confirmed-free endpoints with reserved capacity.

#### Scenario: No reserved capacity
- GIVEN an endpoint does not have reserved capacity
- WHEN probe eligibility is checked
- THEN it is not probed
### Requirement: Isolated probe request

The system SHALL pass a probe only when the response status is `200` and content
is non-empty.

#### Scenario: Non-200 or empty content
- GIVEN a probe response has non-200 status or empty content
- WHEN probe result is evaluated
- THEN `passed` is false
### Requirement: Capability-gated suites

The system SHALL run the basic-text suite for every new endpoint and run
structured-output, tool-calling, vision and long-context suites only when that
capability is claimed and quota reserve allows.

#### Scenario: Unclaimed capability
- GIVEN an endpoint that does not claim tool calling
- WHEN probing runs
- THEN the tool-calling suite is skipped

### Requirement: Probe error handling and promotion

The system SHALL map probe failures deterministically: `402` means paid charge
risk, `429` means quota exhausted, `401/403` means auth/access failure, `5xx`
means provider failure, and any other status means generic probe failure.
HTTP errors raised by the shared OmniRoute client SHALL be persisted as failed
probe results for that endpoint and SHALL NOT crash the whole probing stage.

#### Scenario: Probe error table
- GIVEN probe responses with status `402`, `429`, `401`, `403`, `500`, and another code
- WHEN probe error handling runs
- THEN each response maps to the expected failure reason

#### Scenario: Probe HTTP errors are persisted fail-closed
- GIVEN a confirmed endpoint has reserved capacity
- AND the probe request raises an OmniRoute HTTP error
- WHEN the probing stage runs
- THEN a failed probe row is stored with the HTTP status and mapped reason
- AND the endpoint probe status becomes `failed`
- AND the probing stage completes without crashing
