# role-scorer Specification

## ADDED Requirements

### Requirement: Eligibility filter precedes scoring

The system SHALL score an endpoint for a role only if it has an allowed free
access status, passed the basic probe, has sufficient usable quota, is matched to
a canonical model, has a closed breaker, and supports the role's required
capabilities.

#### Scenario: Breaker open
- GIVEN an eligible-looking endpoint whose breaker is open
- WHEN scoring runs
- THEN the endpoint is rejected before weighted scoring

### Requirement: Additive score without price

The system SHALL compute `score = benchmark_fit + capability_fit + health +
latency + quota_headroom + stability - uncertainty`. Price SHALL NOT be a factor,
because all eligible endpoints are already free within quota.

#### Scenario: Price excluded
- GIVEN two eligible free endpoints
- WHEN they are scored
- THEN no price term influences the score

### Requirement: Artificial Analysis scoring v1

The system SHALL use only `intelligence_index`, `coding_index`, `agentic_index`,
`median_output_tokens_per_second` and `median_end_to_end_seconds`, normalized to
0..1 via P5/P95 clipped min-max (latency inverted). A missing metric SHALL NOT be
treated as 0 — its weight is redistributed and an uncertainty penalty applied; if
all three quality indices are missing the AA quality score is unknown.

#### Scenario: One missing metric
- GIVEN an endpoint missing `coding_index` only
- WHEN the AA subscore is computed
- THEN the coding weight is redistributed and an uncertainty penalty is added

### Requirement: Latency source priority

The system SHALL prefer OmniRoute endpoint telemetry over OmniRoute provider
telemetry over the Artificial Analysis model median for latency.

#### Scenario: Endpoint telemetry available
- GIVEN both endpoint telemetry and an AA median exist
- WHEN latency is scored
- THEN endpoint telemetry is used

### Requirement: Immutable, hash-keyed scores

The system SHALL store each score immutably with an `input_state_hash` and SHALL
skip recomputation when the hash is unchanged.

#### Scenario: Unchanged inputs
- GIVEN an endpoint whose scoring inputs are unchanged
- WHEN scoring runs
- THEN no new score is computed
