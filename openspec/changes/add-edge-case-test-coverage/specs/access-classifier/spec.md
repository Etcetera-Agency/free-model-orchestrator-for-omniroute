# access-classifier Specification

## MODIFIED Requirements

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

### Requirement: Fail closed

The system SHALL fail closed when evidence is missing, empty or stale.

#### Scenario: Empty evidence
- GIVEN no usable evidence is present
- WHEN access is classified
- THEN the endpoint is not classified as usable free access
