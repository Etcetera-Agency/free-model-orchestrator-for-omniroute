# probe-runner Specification

## Purpose
TBD - created by archiving change add-scoring. Update Purpose after archive.
## Requirements
### Requirement: Probe only after free confirmation

The system SHALL probe only confirmed-free endpoints with reserved capacity.
When a provider/account wildcard quota rule confirms many endpoints and live
one-member FMO combos exist, the probing stage SHALL probe those current combo
seed models first instead of probing the entire provider pool in one run.

#### Scenario: No reserved capacity
- GIVEN an endpoint does not have reserved capacity
- WHEN probe eligibility is checked
- THEN it is not probed

#### Scenario: Current combo seeds are probed before wider provider pool
- GIVEN a provider/account wildcard quota rule confirms multiple endpoints
- AND a live one-member FMO combo uses one of those endpoints as seed
- WHEN probing runs
- THEN the seed endpoint is probed
- AND sibling endpoints from the same provider pool are left unprobed for later
  candidate expansion
### Requirement: Isolated probe request

The system SHALL pass a probe only when the response status is `200` and content
is non-empty. Production probes SHALL use the shared OpenAI-compatible
`/v1/chat/completions` route with a tiny completion budget and no-cache header,
because provider-specific provider ids may be management identifiers that are
not valid chat route slugs. Production probes SHALL request streaming mode so
providers that reject OmniRoute-injected `stream_options` on non-stream requests
can still be validated. Streaming probes SHALL use a distinct suite version and
request hash from older non-stream probes, and endpoint `probe_status` SHALL
reflect the stored probe row used for that run. Provider denial text that
indicates unusable free quota (for example "prevent abuse of free resources" or
"accounts that have not been recharged") SHALL fail the probe even when the
upstream returns HTTP 200.

#### Scenario: Non-200 or empty content
- GIVEN a probe response has non-200 status or empty content
- WHEN probe result is evaluated
- THEN `passed` is false

#### Scenario: Free-resource denial content fails probe
- GIVEN a probe response has HTTP 200
- AND the content states the free resource is blocked for abuse prevention or
  unrecharged accounts
- WHEN probe result is evaluated
- THEN `passed` is false

#### Scenario: Streaming probe evidence supersedes old same-day failures
- GIVEN an endpoint has an older same-day failed non-stream probe row
- WHEN the streaming probe succeeds
- THEN a new streaming suite probe row is stored
- AND endpoint `probe_status` is `passed`
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
