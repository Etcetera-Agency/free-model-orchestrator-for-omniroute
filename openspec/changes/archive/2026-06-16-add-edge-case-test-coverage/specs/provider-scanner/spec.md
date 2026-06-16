# provider-scanner Specification

## MODIFIED Requirements

### Requirement: False-removal protection

The system SHALL mark a previously known endpoint removed only after at least two
successful snapshots both omit it and the newest successful omission is at least
five minutes old. Failed snapshots SHALL NOT count toward previous-success or
unchanged-catalog decisions.

#### Scenario: Fewer than two snapshots
- GIVEN fewer than two snapshots exist
- WHEN removal protection evaluates an omitted endpoint
- THEN it does not mark removed

#### Scenario: Not both snapshots successful
- GIVEN the relevant snapshots are not both successful
- WHEN removal protection evaluates an omitted endpoint
- THEN it does not mark removed

#### Scenario: Omission too young
- GIVEN two successful omissions exist but the newest is younger than five minutes
- WHEN removal protection evaluates an omitted endpoint
- THEN it does not mark removed

### Requirement: Daily catalog scan and snapshot

The system SHALL use only successful snapshots as the previous successful
snapshot for unchanged detection.

#### Scenario: Failed snapshot not previous
- GIVEN the latest stored snapshot has non-success fetch status
- WHEN unchanged detection runs
- THEN that snapshot is ignored as previous
