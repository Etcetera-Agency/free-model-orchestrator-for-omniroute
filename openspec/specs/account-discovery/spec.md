# account-discovery Specification

## Purpose
TBD - created by archiving change add-discovery. Update Purpose after archive.
## Requirements
### Requirement: Connections are not capacity

The system SHALL count active credential connections separately from independent
quota pools. Provider capacity SHALL be the sum of usable capacity of independent
quota pools, never the connection count times per-account quota.

#### Scenario: Shared upstream account
- GIVEN 3 OmniRoute connections backed by 1 upstream account
- WHEN capacity is computed
- THEN capacity equals one pool's quota, not three

#### Scenario: Independent accounts
- GIVEN 3 connections proven to be independent accounts
- WHEN capacity is computed
- THEN capacity is the sum of the three pools

### Requirement: Quota pool grouping order

The system SHALL merge endpoints into pools conservatively. If endpoints in one
pool report conflicting independence statuses, merged pool status SHALL be
unknown.

#### Scenario: Conflicting pool statuses
- GIVEN endpoints in the same pool have different independence statuses
- WHEN pools are merged
- THEN the merged status is unknown

### Requirement: Independence status drives capacity

The system SHALL count usable capacity only from confirmed independent
connections and SHALL deduplicate repeated connection ids.

#### Scenario: Non-confirmed and duplicate capacity
- GIVEN capacity candidates include non-confirmed connections and duplicate ids
- WHEN usable capacity is computed
- THEN only unique confirmed independent connection ids count

### Requirement: Connection-source errors are conservative

When connection metadata cannot prove rate-limit availability, the system SHALL
fall back to previous pool keys so capacity grouping stays stable.

#### Scenario: Rate limits unavailable
- GIVEN `rate_limits_available` is false and previous pools exist
- WHEN account discovery runs
- THEN previous pool keys are reused

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
