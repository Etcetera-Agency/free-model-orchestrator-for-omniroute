## MODIFIED Requirements

### Requirement: Daily and event-triggered inventory

The system SHALL run a full Hermes inventory daily. Manual or event-driven runs
MAY request a full Hermes inventory, but an unknown role name alone SHALL NOT
force an immediate inventory run or create a new combo.

#### Scenario: Daily run performs full inventory
- GIVEN the daily scheduler reaches the Hermes inventory window
- WHEN the inventory trigger is evaluated
- THEN a full Hermes inventory is requested

#### Scenario: Manual run can request full inventory
- GIVEN an operator starts a manual run with full Hermes inventory requested
- WHEN the inventory trigger is evaluated
- THEN a full Hermes inventory is requested

#### Scenario: Unknown role event does not create inventory or combo
- GIVEN an event-driven run references an unknown role name
- AND no explicit full inventory request is present
- WHEN the inventory trigger is evaluated
- THEN no immediate inventory run is forced by that role name alone
- AND no new combo is created from the unknown role name
