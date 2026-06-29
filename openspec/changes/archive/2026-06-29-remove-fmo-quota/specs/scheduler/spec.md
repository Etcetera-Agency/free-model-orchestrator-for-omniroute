# scheduler Specification

## MODIFIED Requirements

### Requirement: Daily batch pipeline

The system SHALL execute the full daily pipeline once per day at the configured
cron time, ordered so discovery precedes access classification, scoring,
allocation, combo build, minimal diff, apply, smoke test and audit. Routine
sub-daily (5-min / hourly) cron jobs SHALL NOT be required.

#### Scenario: Scheduled daily run
- GIVEN the configured daily cron time arrives
- WHEN the scheduler fires
- THEN the full pipeline runs end to end in order

## REMOVED Requirements

### Requirement: Weekly tokens-per-request recalibration cadence
**Reason**: FMO no longer converts quota units or maintains a
`tokens_per_request` factor.
**Migration**: OmniRoute owns request-equivalent conversion and recalibration
from request-path usage observations.
