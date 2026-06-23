## MODIFIED Requirements

### Requirement: Minimal diff apply to OmniRoute

The system SHALL compute a minimal diff between the last live OmniRoute combo
state and the desired structured combo member list, persist the diff snapshot,
and apply only managed `fmo-*` combos whose live baseline still matches the saved
`before` state. Applied combo payloads SHALL preserve priority order and SHALL be
sent to OmniRoute as structured model steps when provider/account identity is
known. Drift, unsafe preconditions, smoke-test failure, and rollback behavior
SHALL remain deterministic and fail closed.

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
