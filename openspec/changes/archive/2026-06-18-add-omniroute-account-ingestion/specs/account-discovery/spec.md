## ADDED Requirements

### Requirement: Live OmniRoute connection and account fetch

The system SHALL fetch connections, provider account status, pool membership and
rate-limit availability from the OmniRoute management API before grouping quota
pools, unless connection data is explicitly injected. The fetch SHALL use
configured credentials with bounded retries and structured errors. When the
rate-limit availability fetch fails, the system SHALL group pools conservatively
and SHALL NOT promote connections to independent (`confirmed`) capacity on the
strength of unavailable data.

#### Scenario: Connections fetched before grouping
- GIVEN no connection data is injected and credentials are configured
- WHEN account discovery runs
- THEN connections and rate-limit availability are fetched from OmniRoute
- AND the fetched connections are grouped into quota pools

#### Scenario: Rate-limit fetch unavailable
- GIVEN the rate-limit availability fetch fails
- WHEN quota pools are grouped
- THEN grouping falls back conservatively
- AND no connection is promoted to confirmed independent capacity
