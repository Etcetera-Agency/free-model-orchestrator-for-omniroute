# audit-rollback Specification

## ADDED Requirements

### Requirement: Every run and change is recorded

The system SHALL create a `sync_runs` record per command and a `change_log` entry
per change containing entity type/id, action, before/after JSON, reason codes and
source references.

#### Scenario: Combo change logged
- GIVEN a combo is updated
- WHEN the change is committed
- THEN a change_log entry records before/after, reason codes and source refs

### Requirement: Explainability per assignment

The system SHALL store, for each endpoint-to-role assignment, why it was selected,
why not the next candidate, quota impact, diversity impact, score components and
the constraints checked.

#### Scenario: Inspect an assignment
- GIVEN an endpoint assigned as a role's primary
- WHEN the assignment is audited
- THEN the stored record explains the choice and the rejected alternative

### Requirement: Rollback scopes

The system SHALL support rolling back one combo, all combos of one run, an active
quota rule, or a model match. Catalog snapshots SHALL NOT be rolled back because
they record observation.

#### Scenario: Roll back a run
- GIVEN a run applied several combo changes
- WHEN that run is rolled back
- THEN all its combo changes are reverted from snapshots while catalog snapshots remain
