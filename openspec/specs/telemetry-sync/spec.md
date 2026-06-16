# telemetry-sync Specification

## Purpose
TBD - created by archiving change add-scoring. Update Purpose after archive.
## Requirements
### Requirement: Daily telemetry sync

The system SHALL sync OmniRoute health, telemetry, rate-limit, resilience and
usage data once per day before scoring. Real-time monitoring SHALL NOT be
required; intraday failures are handled by OmniRoute.

#### Scenario: Daily sync before scoring
- GIVEN the daily batch reaches scoring
- WHEN telemetry sync has run
- THEN scoring uses the freshly synced health and latency aggregates

### Requirement: Latency granularity honesty

The system SHALL record latency granularity (provider / account / endpoint) and
SHALL NOT present a provider-level p95 as exact endpoint latency.

#### Scenario: Only provider-level latency
- GIVEN only provider-level p95 is available for an endpoint
- WHEN it is stored
- THEN it is tagged provider-granularity, not endpoint-exact

### Requirement: Degradation rules

The system SHALL mark an endpoint `degraded` on 3 consecutive errors, success
rate below threshold, p95 above the role threshold, or an open breaker, without
disabling the same canonical model on other providers.

#### Scenario: Consecutive failures
- GIVEN an endpoint with 3 consecutive errors
- WHEN degradation is evaluated
- THEN that endpoint is marked degraded but sibling-provider endpoints are not

