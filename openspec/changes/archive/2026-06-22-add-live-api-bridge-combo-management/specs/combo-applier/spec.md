## ADDED Requirements

### Requirement: Apply uses management combo API through the live bridge

The combo applier SHALL read and write live OmniRoute combo state through the
management combo API exposed by the live API bridge. Apply SHALL read the live
combo set with `GET /api/combos` before mutation, SHALL update only existing
`fmo-` combos through the management write route under `/api/combos/{id}`, and
SHALL preserve drift protection, idempotency, read-back verification, smoke
testing through the OpenAI-compatible combo model, rollback, and rebalance-only
behavior.

#### Scenario: Apply reads combos through management API bridge
- GIVEN the apply stage is configured with the live API bridge base URL
- WHEN apply starts
- THEN it reads the live combo set through `GET /api/combos`
- AND it uses that response as the source of truth for existing managed combos

#### Scenario: Apply writes existing combos through management API bridge
- GIVEN an `fmo-` combo exists in the live combo set
- WHEN apply rebalances that combo
- THEN it sends the membership update through the management route under
  `/api/combos/{id}`
- AND it reads the combo back through the management API before reporting
  success

### Requirement: Public combo projection is never used for management apply

FMO SHALL NOT use `/v1/combos` or any other public/projected combo endpoint to
read, write, validate, or roll back managed combo state. Public combo projections
are not a substitute for OmniRoute management auth, management route validation,
or persisted operator-owned combo state.

#### Scenario: Public combo projection is never used for management apply
- GIVEN combo apply needs to read, write, validate, or roll back live combo
  state
- WHEN the applier performs the operation
- THEN every combo-management operation uses `/api/combos*`
- AND no request is sent to `/v1/combos`
