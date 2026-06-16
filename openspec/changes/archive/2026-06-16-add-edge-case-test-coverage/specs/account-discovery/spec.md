# account-discovery Specification

## MODIFIED Requirements

### Requirement: Quota pool grouping order

The system SHALL merge endpoints into pools conservatively. If endpoints in one
pool report conflicting independence statuses, merged pool status SHALL be
unknown.

#### Scenario: Conflicting pool statuses
- GIVEN endpoints in the same pool have different independence statuses
- WHEN pools are merged
- THEN the merged status is unknown

### Requirement: Connection-source errors are conservative

When connection metadata cannot prove rate-limit availability, the system SHALL
fall back to previous pool keys so capacity grouping stays stable.

#### Scenario: Rate limits unavailable
- GIVEN `rate_limits_available` is false and previous pools exist
- WHEN account discovery runs
- THEN previous pool keys are reused

### Requirement: Independence status drives capacity

The system SHALL count usable capacity only from confirmed independent
connections and SHALL deduplicate repeated connection ids.

#### Scenario: Non-confirmed and duplicate capacity
- GIVEN capacity candidates include non-confirmed connections and duplicate ids
- WHEN usable capacity is computed
- THEN only unique confirmed independent connection ids count
