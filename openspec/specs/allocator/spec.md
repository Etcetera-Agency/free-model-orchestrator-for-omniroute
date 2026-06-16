# allocator Specification

## Purpose
TBD - created by archiving change add-allocation. Update Purpose after archive.
## Requirements
### Requirement: Global allocation before combos

The system SHALL allocate the usable capacity of all quota pools across all roles
globally before building any combo, so the same endpoint/account cannot be
counted as guaranteed capacity for several roles at once.

#### Scenario: Shared endpoint across roles
- GIVEN one endpoint eligible for three roles
- WHEN allocation runs
- THEN its quota is not promised in full to all three roles simultaneously

### Requirement: Hard constraints and heavy-role separation

The system SHALL keep heavy roles separated across quota pools when possible and
SHALL NOT assign a second primary for the same heavy role in the same pool.

#### Scenario: Heavy role same pool second primary
- GIVEN a heavy role already has a primary endpoint in a pool
- WHEN another endpoint from the same pool is considered as second primary
- THEN it is not selected
### Requirement: Oversubscription gate

The system SHALL reject plans where assigned demand exceeds usable free capacity.
Zero-capacity pools SHALL be treated as oversubscribed instead of causing a
division error.

#### Scenario: Zero capacity pool
- GIVEN a plan assigns demand to a pool with zero usable capacity
- WHEN the plan is validated
- THEN the plan is rejected as oversubscribed
### Requirement: One priority combo per role, no weights

The system SHALL emit exactly one combo per role as an ordered endpoint list with
`strategy = priority` (index 0 = primary, 1..N = fallback); endpoint weights SHALL
NOT be calculated or stored.

#### Scenario: Combo output
- GIVEN an allocated role
- WHEN its combo is emitted
- THEN it is an ordered priority list with no weights

### Requirement: Degraded modes, no paid fallback

If no free endpoint has enough capacity for a role, the system SHALL omit that
role from the plan rather than allocate paid or unsafe fallback capacity.

#### Scenario: No endpoint with capacity
- GIVEN a role's demand exceeds every matching free endpoint capacity
- WHEN allocation runs
- THEN the role is absent from the plan
### Requirement: Stability

The system SHALL keep stable allocation order when scores drift trivially and
SHALL tolerate endpoints missing from the current score map.

#### Scenario: Missing score during stable order
- GIVEN a previous endpoint is not present in current scores
- WHEN stable order is computed
- THEN no `KeyError` is raised
