# data-model Specification

## MODIFIED Requirements

### Requirement: Canonical status vocabulary

The system SHALL enforce combo state transitions through the allowed transition
set. It SHALL reject direct snapshot-to-commit, applied-to-commit without smoke,
and any backward transition.

#### Scenario: Snapshot directly committed
- GIVEN a combo is in `SNAPSHOT_SAVED`
- WHEN transition to `COMMITTED` is requested
- THEN the transition is rejected

#### Scenario: Applied directly committed
- GIVEN a combo is in `APPLIED`
- WHEN transition to `COMMITTED` is requested
- THEN the transition is rejected

#### Scenario: Backward combo transition
- GIVEN a combo is in any later state
- WHEN transition to an earlier state is requested
- THEN the transition is rejected
