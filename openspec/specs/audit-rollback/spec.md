# audit-rollback Specification

## Purpose
TBD - created by archiving change add-allocation. Update Purpose after archive.
## Requirements
### Requirement: Every run and change is recorded

The system SHALL create a `sync_runs` record per command and a `change_log` entry
per change containing entity type/id, action, before/after JSON, reason codes and
source references.

#### Scenario: Combo change logged
- GIVEN a combo is updated
- WHEN the change is committed
- THEN a change_log entry records before/after, reason codes and source refs

### Requirement: Explainability per assignment

The system SHALL store, for each endpoint-to-role or endpoint-to-cell
assignment, why it was selected, why nearby candidates were not selected, quota
impact, diversity impact, score components, and the structured combo member
identity used to render the OmniRoute payload.

#### Scenario: Inspect an assignment
- GIVEN an endpoint assigned as a combo primary or fallback
- WHEN the assignment is audited
- THEN the audit shows the endpoint id, provider/model, provider account,
  connection id when pinned, quota pool, canonical model/family, score
  components, quota impact, and diversity impact

### Requirement: Rollback scopes

The system SHALL support rolling back one combo, all combos of one run, an active
quota rule, or a model match. Catalog snapshots SHALL NOT be rolled back because
they record observation. The operator `rollback` command SHALL invoke combo
revert — one combo (`--endpoint`/`--role`) or all combos of a run (`--run-id`) —
through the runner's fail-closed gating, restoring each targeted combo to its
persisted pre-change state and recording the revert in audit. The `rollback`
command SHALL NOT revert AA-index threshold migrations; that is owned solely by
`aa-index rollback`. A failing restore SHALL return exit 7 (`rollback_failed`).

#### Scenario: Roll back a run
- GIVEN a run applied several combo changes
- WHEN that run is rolled back
- THEN all its combo changes are reverted from snapshots while catalog snapshots remain

#### Scenario: rollback command reverts combos, not AA-index
- **WHEN** the operator runs `rollback --run-id R`
- **THEN** every applied `fmo-` combo of run R is restored to its persisted
  pre-change state and the revert is recorded in audit
- **AND** no AA-index threshold migration is changed

#### Scenario: rollback restore failure exits 7
- **WHEN** a `rollback` restore call fails
- **THEN** the command returns exit 7 (`rollback_failed`)

