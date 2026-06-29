# dynamic-role-lifecycle Specification

## Purpose
Define role activation and retirement behavior from Hermes inventory.

## Requirements

### Requirement: Role lifecycle follows Hermes inventory
The role lifecycle stage SHALL activate roles with active consumers and mark
missing roles retiring without deleting history.

#### Scenario: Brand-new role
- **WHEN** a new active consumer references a role
- **THEN** the role can become active/bootstrap-pending.

#### Scenario: Role disappears once
- **WHEN** an active role has no active consumers
- **THEN** it is marked retiring.

#### Scenario: Role reappears within grace
- **WHEN** a retiring role reappears in inventory
- **THEN** it returns to active.
