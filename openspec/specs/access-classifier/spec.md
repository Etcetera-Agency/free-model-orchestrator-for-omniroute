# access-classifier Specification

## Purpose
TBD - created by archiving change add-quota. Update Purpose after archive.
## Requirements
### Requirement: Ordered free/exclusion classification

The system SHALL evaluate permanent exclusions and manual denial before any
zero-price evidence. A removed or permanently broken endpoint SHALL remain
excluded even if price is zero. A manually denied endpoint SHALL remain denied
even if price is zero.

#### Scenario: Removed beats zero price
- GIVEN an endpoint is removed or permanently broken and also has zero price
- WHEN access is classified
- THEN the exclusion status is returned

#### Scenario: Manual deny beats zero price
- GIVEN an endpoint has manual deny evidence and zero price
- WHEN access is classified
- THEN manual deny is returned
### Requirement: Free-quota preconditions

The system SHALL treat free quota as usable only when a quota rule exists, hard
stop is true, limit, remaining and reset time are present, promotion has not
expired, and remaining quota is greater than the safety buffer.

#### Scenario: Exhausted by safety buffer
- GIVEN remaining quota is less than or equal to the safety buffer
- WHEN access is classified
- THEN the endpoint is classified as `free_quota_exhausted`

#### Scenario: Missing quota precondition
- GIVEN a quota rule exists but hard stop is false or limit, remaining or reset time is missing
- WHEN access is classified
- THEN the endpoint is classified as `missing_quota_precondition`

#### Scenario: Promotion expired
- GIVEN free access depends on a promotion whose end time is in the past
- WHEN access is classified
- THEN the endpoint is classified as `promotion_expired`
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

The system SHALL fail closed when evidence is missing, empty or stale.
During batch access classification, missing quota evidence for one endpoint SHALL
be stored as endpoint-local `unknown` state with `quota_rule_missing`; it SHALL
NOT abort classification for other endpoints that have usable quota evidence.

#### Scenario: Empty evidence
- GIVEN no usable evidence is present
- WHEN access is classified
- THEN the endpoint is not classified as usable free access

#### Scenario: Missing endpoint-local quota evidence fails closed
- GIVEN one endpoint has an active usable quota rule
- AND another endpoint has no quota rule
- WHEN access classification runs over both endpoints
- THEN the endpoint with the rule is classified normally
- AND the endpoint without the rule is stored as `unknown` with
  `quota_rule_missing`
- AND the stage succeeds so downstream stages can use confirmed endpoints
