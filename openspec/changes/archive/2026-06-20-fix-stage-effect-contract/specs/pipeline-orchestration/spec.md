## MODIFIED Requirements

### Requirement: Ordered pipeline run

The system SHALL provide a pipeline runner that executes the orchestrator stages
in the canonical order (external metadata sync, free candidate discovery, model
matching, quota research and access classification, probing, telemetry and quota
sync, role scoring, allocation, diff, apply, audit) within a single run, driven
by the existing stage modules rather than reimplementing them. A full run SHALL
record each stage's real module outcome and SHALL fail or stop according to that
outcome. A stage SHALL report `success` only when it produced its declared,
observable effect — a repository write, an OmniRoute call, or an explicit
idempotent no-change decision. A stage that returns `success` without its
declared effect SHALL be rejected by the executable test suite.

#### Scenario: Stages run in order
- **WHEN** a full run is invoked
- **THEN** stages execute in the canonical order
- **AND** each stage records its real module outcome against the run

#### Scenario: Run is identified
- **WHEN** a run is started
- **THEN** a run record with a run id is persisted via the repository layer

#### Scenario: Full run calls production adapters
- **WHEN** a full run is invoked through the composed runtime
- **THEN** every wired canonical stage adapter is invoked exactly in canonical order
- **AND** replacing a required adapter with an unconditional success helper fails
  the executable test suite

#### Scenario: Stage success requires a real effect
- **WHEN** a wired stage adapter returns `success`
- **THEN** its declared side effect is observable (a repository row written, an
  OmniRoute call recorded, or an explicit idempotent no-change decision)
- **AND** an adapter that returns `success` without producing its declared effect
  fails the executable test suite

### Requirement: Fail-closed gating

The runner SHALL stop downstream apply when a safety gate fails, and SHALL NOT
feed partial or stale stage output into dependent stages. The runner SHALL never
call `/api/combos/test`. Any stage adapter that cannot fetch, validate, persist,
or verify its required evidence SHALL return a non-success status instead of
fabricating success. A canonical stage that is not yet wired to its domain
module SHALL return a non-success `not_implemented` status and SHALL stop the run
before any dependent stage; the runner SHALL NOT provide a catch-all adapter
that returns success for unwired stages.

#### Scenario: Failed gate stops apply
- **WHEN** a safety gate (quota, snapshot, validation, probe) fails
- **THEN** apply does not run and the run reports the failing gate

#### Scenario: Partial data not consumed
- **WHEN** a stage returns partial or stale output
- **THEN** dependent stages do not consume it and the run is marked partial/stale

#### Scenario: No combo test call
- **WHEN** the pipeline applies combos
- **THEN** `/api/combos/test` is not called

#### Scenario: Unwired stage fails closed
- **WHEN** a canonical stage is not yet wired to its domain module
- **THEN** it returns a non-success `not_implemented` status
- **AND** the run stops at that stage with a non-success exit code
- **AND** no downstream stage reports fabricated success
