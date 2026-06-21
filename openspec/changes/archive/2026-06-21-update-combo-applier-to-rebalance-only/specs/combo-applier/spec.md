# combo-applier Specification

## ADDED Requirements

### Requirement: Rebalance only existing combos; never create or delete

The system SHALL rebalance the membership of OmniRoute combos that already exist
in the live combo set and SHALL NOT create or delete any combo. Combo existence
SHALL be decided only from the live OmniRoute combo set
(`_read_current_combos`), never from persisted state, because the operator may
create a combo by hand and a known combo may have been removed upstream.

A desired `fmo-` change whose combo id is absent from the live set SHALL be
skipped and reported as `unmanaged_combo`; skipping an absent combo SHALL NOT
fail the run, and every other present combo in the same apply SHALL still be
rebalanced. The applier SHALL issue no DELETE on any path (success, drift, or
rollback). Drift protection, the smoke path, rollback, and the `fmo-` scoping all
remain in force for combos that exist.

#### Scenario: Non-existent combo is not created
- GIVEN a desired `fmo-` diff whose combo id is absent from the live OmniRoute
  combo set
- WHEN apply runs
- THEN no `POST /api/combos/{id}` is issued for that combo
- AND it is reported as `unmanaged_combo`

#### Scenario: Absent combo is skipped without failing the run
- GIVEN one desired combo that exists and one that is absent
- WHEN apply runs
- THEN the existing combo is rebalanced and smoke-tested
- AND the absent combo is skipped, and the run is not failed by the skip

#### Scenario: Combos are never deleted
- GIVEN any apply outcome (success, drift, or rollback)
- WHEN apply runs
- THEN no combo delete request is issued to OmniRoute
