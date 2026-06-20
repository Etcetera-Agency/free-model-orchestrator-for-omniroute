## ADDED Requirements

### Requirement: Hermes inventory is gathered in production

The production pipeline SHALL run a `hermes-inventory` stage that gathers the
role registry, consumers, schedules, and observed `calls_per_run` through the
deterministic adapter selected by `HERMES_INVENTORY_MODE`, and persist them
through the repository. The Inspector forecast SHALL run prompt-only over the
shared runtime and SHALL NOT read Hermes sources itself. Missing required Hermes
env SHALL fail closed; an unknown role SHALL bootstrap through the dynamic-role
path. The stage SHALL report `success` only when inventory rows are persisted.

#### Scenario: Inventory persisted from the selected mode
- **WHEN** the `hermes-inventory` stage runs with `HERMES_INVENTORY_MODE` set
- **THEN** roles, consumers, schedules, and observed cadence are gathered via the
  matching adapter and persisted
- **AND** an adapter returning success without persisting inventory fails the suite

#### Scenario: Inspector is prompt-only
- **WHEN** the Inspector forecast runs
- **THEN** it receives only the assembled prompt over the shared runtime
- **AND** it performs no direct source reads

#### Scenario: Missing Hermes env fails closed
- **WHEN** required Hermes env is missing
- **THEN** the stage fails closed and no inventory is written
