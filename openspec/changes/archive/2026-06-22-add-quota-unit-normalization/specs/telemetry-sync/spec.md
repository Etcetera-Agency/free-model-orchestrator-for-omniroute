## ADDED Requirements

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
