# dynamic-role-lifecycle Specification

## Purpose
TBD - created by archiving change add-role-lifecycle. Update Purpose after archive.
## Requirements
### Requirement: Reconcile, never hardcode

The system SHALL continuously reconcile the desired Hermes role set with managed
OmniRoute combos: discover desired roles, create missing managed roles, update
active roles, mark missing roles retiring, and delete only after a grace period
and zero observed use. A role SHALL NOT be deleted immediately after disappearing
from a single scan.

#### Scenario: Role disappears once
- GIVEN a role missing from one daily inventory
- WHEN reconciliation runs
- THEN the role is marked retiring, not deleted

### Requirement: Removed-role grace and reactivation

The system SHALL mark an unused role inactive with `missing_since` and keep its
current combo during the grace period; if the role reappears it SHALL become
active again and clear `missing_since`. Combo deletion is allowed only after the
grace period and no recent runtime usage.

#### Scenario: Role reappears within grace
- GIVEN a retiring role within its grace period
- WHEN it is used again
- THEN it is reactivated and its combo is retained

### Requirement: New-role bootstrap

The system SHALL bootstrap a newly discovered role using a role policy template
and cold-start demand, then run normal allocation. Roles in `retiring` SHALL keep
their current combo but receive no speculative capacity expansion.

#### Scenario: Brand-new role
- GIVEN a role discovered for the first time
- WHEN it is onboarded
- THEN it gets a template policy and cold-start demand before allocation

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

