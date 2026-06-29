# account-discovery Specification

## Purpose
TBD - created by archiving change add-discovery. Update Purpose after archive.
## Requirements
### Requirement: Connections are not capacity

The system SHALL count active credential connections separately from independent
account scopes. Provider capacity SHALL be the sum of usable capacity of
independent account scopes, never the connection count times per-account
capacity.

#### Scenario: Shared upstream account
- GIVEN 3 OmniRoute connections backed by 1 upstream account
- WHEN capacity is computed
- THEN capacity equals one account scope's capacity, not three

#### Scenario: Independent accounts
- GIVEN 3 connections proven to be independent accounts
- WHEN capacity is computed
- THEN capacity is the sum of the three account scopes

### Requirement: Account scope grouping order

The system SHALL merge endpoints into account scopes conservatively. If
endpoints in one scope report conflicting independence statuses, merged scope
status SHALL be unknown.

#### Scenario: Conflicting scope statuses
- GIVEN endpoints in the same account scope have different independence statuses
- WHEN account scopes are merged
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
fall back to previous account-scope keys so capacity grouping stays stable.

#### Scenario: Rate limits unavailable
- GIVEN `rate_limits_available` is false and previous account scopes exist
- WHEN account discovery runs
- THEN previous account-scope keys are reused

### Requirement: Live OmniRoute connection and account fetch

The system SHALL fetch connections, provider account status, account-scope
membership and rate-limit availability from the OmniRoute management API before
grouping account scopes, unless connection data is explicitly injected. The fetch SHALL use
configured credentials with bounded retries and structured errors. When the
rate-limit availability fetch fails, the system SHALL group scopes conservatively
and SHALL NOT promote connections to independent (`confirmed`) capacity on the
strength of unavailable data.

#### Scenario: Connections fetched before grouping
- GIVEN no connection data is injected and credentials are configured
- WHEN account discovery runs
- THEN connections and rate-limit availability are fetched from OmniRoute
- AND the fetched connections are grouped into account scopes

#### Scenario: Rate-limit fetch unavailable
- GIVEN the rate-limit availability fetch fails
- WHEN account scopes are grouped
- THEN grouping falls back conservatively
- AND no connection is promoted to confirmed independent capacity

### Requirement: Fingerprint-backed account scopes

The system SHALL expand any OmniRoute provider connection that exposes
`providerSpecificData.fingerprints` as registered account identities into one
provider-account scope per unique fingerprint. Each fingerprint scope SHALL use
a stable scope key, SHALL preserve the parent OmniRoute connection id in
metadata, and SHALL count as confirmed independent account capacity without
hard-coding provider names.

#### Scenario: Fingerprints create independent scopes
- GIVEN an OmniRoute provider connection contains three unique
  `providerSpecificData.fingerprints`
- WHEN account discovery expands account scopes
- THEN three confirmed fingerprint-backed account scopes are created for that
  provider
- AND provider capacity can treat the three scopes independently

#### Scenario: Fingerprint scopes feed allocation independently
- GIVEN an OmniRoute provider connection contains three unique
  `providerSpecificData.fingerprints`
- AND endpoints are discovered for that provider's models
- WHEN allocation builds candidate groups for combos
- THEN endpoints from separate fingerprint-backed scopes can be placed into
  combos independently

#### Scenario: Duplicate fingerprints are deduplicated
- GIVEN a provider connection reports the same account fingerprint more than once
- WHEN account discovery expands fingerprint-backed scopes
- THEN only one provider-account scope is created for that fingerprint

#### Scenario: Missing fingerprints stay shared
- GIVEN a provider connection has no `providerSpecificData.fingerprints`
- AND it has no top-level independent account evidence
- WHEN account discovery expands account scopes
- THEN the connection remains on the existing shared account-scope path
- AND capacity is not multiplied by the connection count
