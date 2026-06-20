# pipeline-orchestration Specification

## ADDED Requirements

### Requirement: Account discovery runs in the pipeline and produces real effects

The composed runtime SHALL include an `account-discovery` stage that drives the
`account-discovery` domain module (`discover_live_accounts` / quota-pool
grouping) against the OmniRoute management API and persists pool membership and
independence status (`confirmed | inferred | assumed_shared | unknown`) through
the repository. The stage SHALL run after candidate discovery and before
quota-sync and scoring, so allocation consumes confirmed-independence capacity.
The stage SHALL report `success` only when its declared persistence effect is
observable, and SHALL fail closed (conservative grouping, no `confirmed`
promotion) when rate-limit availability data is unavailable.

#### Scenario: Account discovery persists quota pools
- **WHEN** the `account-discovery` stage runs
- **THEN** quota-pool membership and independence status are persisted through
  the repository
- **AND** an adapter returning success without writing pool rows fails the suite

#### Scenario: Account discovery ordered before allocation inputs
- **WHEN** the canonical pipeline runs
- **THEN** `account-discovery` runs after candidate discovery and before
  quota-sync and scoring

#### Scenario: Unavailable rate-limit data stays conservative
- **WHEN** the rate-limit availability fetch fails during the stage
- **THEN** pools are grouped conservatively
- **AND** no connection is promoted to `confirmed` independent capacity
