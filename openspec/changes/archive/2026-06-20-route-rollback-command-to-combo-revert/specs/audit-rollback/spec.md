## MODIFIED Requirements

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
