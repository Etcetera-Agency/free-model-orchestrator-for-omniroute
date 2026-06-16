# role-scorer Specification

## MODIFIED Requirements

### Requirement: Eligibility filter precedes scoring

The system SHALL score an endpoint for a role only if it has an allowed free
access status, passed the basic probe, has sufficient usable quota greater than
zero, is matched to a canonical model, has a closed breaker, and supports the
role's required capabilities. Each rejection branch SHALL expose a distinct
reason.

#### Scenario: Breaker not closed
- GIVEN an otherwise eligible endpoint whose breaker is not closed
- WHEN scoring eligibility runs
- THEN it is rejected with a breaker reason

#### Scenario: Zero quota boundary
- GIVEN an endpoint has usable quota equal to zero
- WHEN scoring eligibility runs
- THEN it is rejected with a quota reason

#### Scenario: Missing required capability
- GIVEN an endpoint lacks a role-required capability
- WHEN scoring eligibility runs
- THEN it is rejected with a capability reason

### Requirement: Artificial Analysis scoring v1

The system SHALL use only `intelligence_index`, `coding_index`, `agentic_index`,
`median_output_tokens_per_second` and `median_end_to_end_seconds`, normalized to
0..1 via P5/P95 clipped min-max (latency inverted). If P95 is less than or equal
to P5, normalized value SHALL be `0.0`. A missing metric SHALL NOT be treated as
0.

#### Scenario: Degenerate percentile range
- GIVEN P95 is less than or equal to P5
- WHEN a metric is normalized
- THEN the normalized value is `0.0`

### Requirement: Latency source priority

The system SHALL prefer OmniRoute endpoint telemetry over OmniRoute provider
telemetry over the Artificial Analysis model median for latency. If all latency
sources are missing, latency source SHALL be unknown.

#### Scenario: No latency source
- GIVEN endpoint telemetry, provider telemetry and AA median are all missing
- WHEN latency source is selected
- THEN no source is selected
