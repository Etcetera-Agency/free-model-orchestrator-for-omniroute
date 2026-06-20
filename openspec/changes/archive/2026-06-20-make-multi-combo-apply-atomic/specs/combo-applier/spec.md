## ADDED Requirements

### Requirement: Multi-combo apply is all-or-nothing

When an apply run mutates more than one `fmo-` combo, the run SHALL be
all-or-nothing. No combo SHALL be mutated in OmniRoute without a persisted record
that makes it recoverable for rollback and visible to the `audit` stage. If any
combo in the run fails its smoke test, every combo already applied in that run
SHALL be restored to its pre-change state before the stage returns. The stage
SHALL report `apply_failed_rolled_back` (exit 6) when the partial apply is fully
rolled back, and `rollback_failed` (exit 7) when any restore call fails.

#### Scenario: Later combo failure rolls back earlier applied combos
- **GIVEN** a run that applies combo A successfully and then fails the smoke test
  on combo B
- **WHEN** the failure is handled
- **THEN** both combo A and combo B are restored to their pre-change state in
  OmniRoute
- **AND** the stage reports `apply_failed_rolled_back` (exit 6)

#### Scenario: No combo is mutated without a persisted record
- **WHEN** a combo is successfully applied in a multi-combo run
- **THEN** a persisted record for that combo exists before the next combo is
  applied, so a subsequent failure can roll it back and `audit` can see it

#### Scenario: Restore failure during partial rollback
- **GIVEN** a partial apply must be rolled back and a restore call raises
- **WHEN** the rollback runs
- **THEN** the stage reports `rollback_failed` (exit 7)
