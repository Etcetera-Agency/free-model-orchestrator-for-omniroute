## ADDED Requirements

### Requirement: Live telemetry fetch

The system SHALL fetch usage, latency, failure and trace telemetry before
normalization from OmniRoute `GET /api/usage/analytics` (and
`GET /api/usage/call-logs`) and/or the Hermes `state.db` session store, unless
telemetry is explicitly injected. The fetch SHALL use
configured credentials with bounded retries and structured errors. When a
telemetry source is unavailable, the system SHALL proceed without fabricating
metrics, leaving the affected latency/failure inputs unknown.

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
