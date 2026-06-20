## ADDED Requirements

### Requirement: Scoring, allocation, and diff stages produce real effects

The composed runtime SHALL drive the `role-scoring`, `allocation`, and `diff`
stages through their existing domain modules and persist their real output. The
`allocation` stage SHALL apply global allocation across all roles, heavy-role
separation, the oversubscription gate, one priority combo per role, and
deterministic stable ordering, with no paid fallback in degraded modes. The
`diff` stage SHALL compute the minimal change against current OmniRoute state
without mutating OmniRoute. Each stage SHALL report `success` only when its
declared effect is observable.

#### Scenario: Scoring persists per-role scores
- **WHEN** the `role-scoring` stage runs
- **THEN** per-role endpoint scores are persisted through the repository
- **AND** an adapter returning success without writing scores fails the suite

#### Scenario: Allocation persists one combo plan per role
- **WHEN** the `allocation` stage runs
- **THEN** `allocation_plans` rows are persisted with targets and constraint report
- **AND** each role receives exactly one priority combo with stable ordering

#### Scenario: Oversubscription gate blocks zero-capacity pool
- **WHEN** allocation encounters a pool with zero confirmed-free capacity
- **THEN** the role is degraded with no paid fallback
- **AND** the constraint report records the blocked pool

#### Scenario: Diff is computed without mutating OmniRoute
- **WHEN** the `diff` stage runs
- **THEN** the minimal change against current OmniRoute state is persisted
- **AND** no OmniRoute mutation call is made during diff
