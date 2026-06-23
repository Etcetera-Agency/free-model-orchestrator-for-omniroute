## MODIFIED Requirements

### Requirement: Transactional apply with smoke test

The system SHALL apply changes under the `combo_apply` advisory lock by:
re-reading current state, verifying its hash is unchanged, saving a snapshot,
applying create/update, reading the combo back, comparing to desired, running a
smoke test via the combo model name, and only then committing the change record.
The diff snapshot SHALL compare and persist the last live OmniRoute combo state
against the desired structured combo member list, and apply only managed `fmo-*`
combos whose live baseline still matches the saved structured `before` state.
Applied combo payloads SHALL preserve priority order and SHALL be sent to
OmniRoute as structured model steps when provider/account identity is known.
Drift, unsafe preconditions, smoke-test failure, and rollback behavior SHALL
remain deterministic and fail closed.

#### Scenario: State changed under us
- GIVEN the current combo hash changed since planning
- WHEN apply starts
- THEN the apply aborts rather than overwrite the newer state

#### Scenario: Structured combo steps applied
- **GIVEN** an allocation target includes `providerId`, `model`, and
  `connectionId`
- **WHEN** apply updates the managed combo
- **THEN** the OmniRoute `PUT /api/combos/{id}` payload contains structured model
  steps preserving those fields

#### Scenario: Endpoint ids retained for audit
- **WHEN** the diff snapshot stores structured `before` and `after` members
- **THEN** it also stores endpoint-id audit fields so rollback/audit can explain
  which provider endpoint each member came from

#### Scenario: Drift guard uses structured baseline
- **GIVEN** the live structured combo differs from the saved structured `before`
  state
- **WHEN** apply runs
- **THEN** apply fails as `combo_drift_detected` and does not overwrite the combo
