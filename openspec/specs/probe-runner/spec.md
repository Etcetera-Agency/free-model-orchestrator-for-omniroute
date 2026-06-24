# probe-runner Specification

## Purpose
TBD - created by archiving change add-scoring. Update Purpose after archive.
## Requirements
### Requirement: Probe only after free confirmation

The system SHALL probe only confirmed-free endpoints with reserved capacity.
When a provider/account wildcard quota rule confirms many endpoints and live
one-member FMO combos exist, the probing stage SHALL probe those current combo
seed models first instead of probing the entire provider pool in one run.
The explicit operator sweep command MAY probe stored endpoints for one provider
with limit, offset, delay, timeout, dry-run, and force controls; this SHALL NOT
widen the default pipeline probing stage.

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

#### Scenario: Operator sweep probes provider catalog explicitly
- GIVEN a provider has stored endpoint rows
- WHEN an operator runs `sweep-provider-models --provider <provider>`
- THEN the command probes the selected provider endpoints through OmniRoute's
  `/api/models/test` endpoint with the stored provider id, model id, and
  connection id
- AND endpoint `probe_status` is updated from the stored probe result
- AND the default `probe-models` stage remains seed-bounded
### Requirement: Isolated probe request

The system SHALL pass a probe only when OmniRoute's model-test result for that
model is `status='ok'`. Production daily probes SHALL call OmniRoute's
`/api/models/test-all` endpoint instead of hand-rolled chat completions, using
explicit active model ids from the current live catalog. The stage SHALL group
eligible models by provider and connection, send batches of at most 100
`modelIds`, set `respectRateLimit=true`, set `autoHideFailed=true`, and include
the no-cache header. Daily probes SHALL skip model aliases whose final path
segment ends with `-auto`. Each returned model entry SHALL be persisted as an
individual `endpoint_probes` row, and endpoint `probe_status` SHALL reflect that
stored probe row. If OmniRoute auto-hides any hard-failed model during
`test-all`, that same required post-test catalog reread SHALL let the normal
catalog scanner tombstone removed models in the same run.

#### Scenario: Non-200 or empty content
- GIVEN a model-test entry has `status='error'`
- WHEN probe result is evaluated
- THEN `passed` is false

#### Scenario: Daily probe uses OmniRoute batch model test
- GIVEN confirmed-free endpoints with reserved capacity across provider
  connections
- WHEN the daily probe stage runs
- THEN it sends `/api/models/test-all` requests grouped by provider and
  connection
- AND every request contains at most 100 `modelIds`
- AND every request sets `respectRateLimit=true` and `autoHideFailed=true`
- AND every returned model result is persisted as one endpoint probe row

#### Scenario: Daily probe skips auto aliases
- GIVEN active confirmed-free models include a model id whose final path segment
  ends with `-auto`
- WHEN the daily probe stage builds `/api/models/test-all` batches
- THEN the `-auto` model id is omitted from every `modelIds` payload
- AND the stored endpoint remains unprobed rather than tombstoned

#### Scenario: Batch failures are persisted fail-closed
- GIVEN `/api/models/test-all` returns a rate-limited entry for one model
- AND omits another requested model because the batch stopped early
- WHEN the daily probe stage records results
- THEN the rate-limited model is stored as failed with HTTP `429`
- AND the missing model is stored as failed with reason
  `missing_model_test_result`

#### Scenario: Daily probe refreshes catalog after model test
- GIVEN `/api/models/test-all` has returned probe results
- WHEN the daily probe stage completes that batch
- THEN FMO immediately rereads `/api/providers` and `/v1/models`
- AND models removed from the active live catalog are tombstoned through the
  normal catalog scanner

#### Scenario: Model-test probe evidence supersedes old same-day failures
- GIVEN an endpoint has an older same-day failed non-stream probe row
- WHEN the OmniRoute model-test probe succeeds
- THEN a new model-test suite probe row is stored
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
