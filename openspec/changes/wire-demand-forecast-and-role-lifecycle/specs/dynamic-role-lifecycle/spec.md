## ADDED Requirements

### Requirement: Role lifecycle is reconciled in production

The production pipeline SHALL reconcile the `roles` table against the live role
registry on each run: removed roles enter a grace window, roles reappearing
within grace are reactivated, and brand-new roles are bootstrapped. Roles SHALL
never be hardcoded; reconcile decisions SHALL be persisted.

#### Scenario: Removed role enters grace
- **WHEN** a role disappears from the live registry
- **THEN** it is marked removed with a grace window rather than deleted

#### Scenario: Role reactivated within grace
- **WHEN** a removed role reappears within its grace window
- **THEN** it is reactivated without a fresh bootstrap

#### Scenario: New role bootstrapped
- **WHEN** a brand-new role is observed
- **THEN** it is bootstrapped through the dynamic-role path and persisted
