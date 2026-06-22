## MODIFIED Requirements

### Requirement: Global allocation before combos

The system SHALL allocate the usable capacity of all quota pools across all roles
globally before building any combo, so the same endpoint/account cannot be
counted as guaranteed capacity for several roles at once. Allocation SHALL reserve
pool capacity for every endpoint that becomes a member of a role's combo — the
primary AND every fallback scored member — not only the primary, so an emitted
combo never promises capacity its pools lack. A would-be combo member whose pool
has no remaining capacity after prior reservations SHALL be dropped from the
combo rather than emitted.

#### Scenario: Shared endpoint across roles
- GIVEN one endpoint eligible for three roles
- WHEN allocation runs
- THEN its quota is not promised in full to all three roles simultaneously

#### Scenario: Fallback members reserve their pool capacity
- GIVEN a role whose combo would include a primary and a fallback from the same
  pool
- WHEN allocation runs
- THEN both members reserve capacity against that pool
- AND the pool usage reflects the primary and the fallback, not just the primary

#### Scenario: Combo member without pool capacity is dropped
- GIVEN a candidate fallback endpoint whose pool capacity is already fully
  reserved
- WHEN the priority combo is built
- THEN that candidate is dropped from the combo
- AND the combo does not promise capacity the pool lacks
