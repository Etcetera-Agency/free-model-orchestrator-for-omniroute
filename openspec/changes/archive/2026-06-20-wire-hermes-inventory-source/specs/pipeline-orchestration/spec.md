## ADDED Requirements

### Requirement: Hermes inventory feeds the pipeline before allocation

The canonical stage order SHALL include `hermes-inventory` ahead of
`role-scoring`, and downstream demand SHALL be derived from the gathered Hermes
inventory rather than only static `expected_load`. A schedule change in Hermes
SHALL trigger a forecast-input refresh on the next run.

#### Scenario: Inventory precedes scoring
- **WHEN** a `full` run executes
- **THEN** `hermes-inventory` runs before `role-scoring`
- **AND** allocation demand reflects the gathered Hermes cadence

#### Scenario: Schedule change refreshes forecast inputs
- **WHEN** a Hermes schedule changes between runs
- **THEN** the next run refreshes the affected forecast inputs
