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

### Requirement: Live telemetry fetch

The system SHALL fetch usage, latency, failure and trace telemetry before
normalization from OmniRoute `GET /api/usage/analytics` (and
`GET /api/usage/call-logs`) and/or the Hermes `state.db` session store, unless
telemetry is explicitly injected. The fetch SHALL use configured credentials
with bounded retries and structured errors. When a telemetry source is
unavailable, the system SHALL proceed without fabricating metrics, leaving the
affected latency/failure inputs unknown.

#### Scenario: Telemetry fetched before normalization
- GIVEN no telemetry is injected and a telemetry source is configured
- WHEN telemetry sync runs
- THEN usage/latency/failure data is fetched from the configured source
- AND the fetched data is normalized into the telemetry model

#### Scenario: Telemetry source unavailable
- GIVEN the telemetry source is unavailable
- WHEN telemetry sync runs
- THEN no metrics are fabricated
- AND the affected latency/failure inputs remain unknown

### Requirement: Telemetry token capture
The system SHALL capture token counts per provider and model from OmniRoute usage analytics without fabricating missing token data.

#### Scenario: Analytics token counts captured
- **GIVEN** OmniRoute usage analytics includes token-count fields for provider or model rows
- **WHEN** telemetry sync normalizes analytics
- **THEN** token counts are stored on the telemetry metric beside request counts

#### Scenario: Missing analytics token counts stay unknown
- **GIVEN** OmniRoute usage analytics omits token-count fields for a row
- **WHEN** telemetry sync normalizes analytics
- **THEN** the telemetry metric keeps tokens unknown instead of fabricating zero
