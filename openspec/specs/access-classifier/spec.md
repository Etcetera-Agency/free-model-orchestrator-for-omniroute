# access-classifier Specification

## Purpose
TBD - created by archiving change add-quota. Update Purpose after archive.
## Requirements
### Requirement: Ordered free/exclusion classification

The system SHALL classify each endpoint, in order, as: `unavailable` (disabled/
removed/permanently broken); `free_unlimited` (confirmed zero price, no other paid
component); `free_quota_available` (paid list price but valid rule and live
remaining); `free_promotional_available` / `free_promotional_expired`; otherwise
`paid_only_excluded`, `unknown_excluded`, or `free_quota_exhausted`. The result
is written to `endpoint_access_states`.

#### Scenario: Zero price
- GIVEN an endpoint with confirmed input/output price 0 and no other paid component
- WHEN classification runs
- THEN it is classified `free_unlimited`

### Requirement: Free-quota preconditions

The system SHALL classify `free_quota_available` only when there is a known limit,
a known remaining or reliable local counter, a known reset, a possible hard stop,
and an unexhausted safety buffer.

#### Scenario: Unknown reset
- GIVEN a rule with a known limit but no known reset
- WHEN classification runs
- THEN the endpoint is not `free_quota_available`

### Requirement: Trust order

The system SHALL resolve conflicting evidence in trust order: manual deny > live
provider quota API > OmniRoute rate-limit state > official active quota rule >
explicit zero pricing > provider flag > models.dev price. A models.dev price
SHALL NOT prove free access for a specific account.

#### Scenario: Live API overrides models.dev
- GIVEN models.dev lists price 0 but the live provider quota API reports a paid charge
- WHEN classification runs
- THEN the live API wins and the endpoint is not treated as free

### Requirement: Fail closed

The system SHALL classify `unknown_excluded` on schema error, stale evidence, or
unknown remaining.

#### Scenario: Stale evidence
- GIVEN the only evidence is stale
- WHEN classification runs
- THEN the endpoint is `unknown_excluded`

