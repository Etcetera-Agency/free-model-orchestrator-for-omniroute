# pipeline-orchestration Specification

## MODIFIED Requirements

### Requirement: Ordered pipeline run

The system SHALL provide a pipeline runner that executes the orchestrator stages
in the canonical order (external metadata sync, free candidate discovery,
account discovery, model matching, access classification, probing, telemetry,
Hermes inventory, role lifecycle, role scoring, demand forecast, allocation,
diff, apply, audit) within a single run, driven by the existing stage modules
rather than reimplementing them. Quota research and quota sync SHALL NOT be
canonical FMO stages. A full run SHALL record each stage's real module outcome
and SHALL fail or stop according to that outcome. A stage SHALL report `success`
only when it produced its declared, observable effect — a repository write, an
OmniRoute call, or an explicit idempotent no-change decision. A stage that
returns `success` without its declared effect SHALL be rejected by the executable
test suite.

#### Scenario: Stages run in order
- **WHEN** a full run is invoked
- **THEN** stages execute in the canonical order without `quota-research` or
  `quota-sync`
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

### Requirement: Live catalog preflight

The composed runtime SHALL refresh OmniRoute's current provider/account/model
catalog before any FMO command or scheduled pipeline uses local repository state
to make decisions. The refresh SHALL read `GET /api/providers` and `GET
/v1/models`, persist active/inactive provider and account state, tombstone
cached endpoints absent from the active live catalog, and clear tombstones for
models that reappear. Matching, access classification, probing, telemetry, role
scoring, allocation, diff, apply, diagnostics, profile normalization, and
operator sweeps SHALL treat the local FMO repository as cache after that refresh,
not as the availability source of truth.

If the live catalog refresh fails, decision-making commands SHALL fail closed as
an external dependency failure rather than using stale cached availability.

#### Scenario: Command refreshes live catalog first
- **WHEN** an operator runs any decision-making FMO command such as
  `score-roles`, `allocate`, `apply`, or `sweep-provider-models`
- **THEN** the runtime refreshes the live OmniRoute provider/model catalog before
  the command stage reads endpoint candidates
- **AND** disabled or missing live provider/model rows are excluded from that
  command

#### Scenario: Scheduled run refreshes live catalog first
- **WHEN** a scheduled full pipeline starts
- **THEN** the first recorded stage refreshes live OmniRoute provider/model
  availability
- **AND** downstream stages consume only the refreshed cache state

#### Scenario: Refresh failure fails closed
- **GIVEN** OmniRoute provider/model catalog fetch fails or returns invalid
  payload
- **WHEN** an FMO command would otherwise use cached endpoint rows
- **THEN** the command exits with external dependency failure
- **AND** no stale cached endpoint is probed, scored, allocated, or applied

### Requirement: Idempotent stage skipping

The runner SHALL skip a stage whose idempotency key (catalog snapshot, probe,
combo apply) matches a prior successful result, so a re-run with unchanged inputs
applies no combo change and re-runs no unchanged probe. FMO SHALL NOT maintain
quota-source or quota-rule idempotency keys.

#### Scenario: Unchanged re-run skips work
- **WHEN** the same run repeats with an unchanged stage idempotency key
- **THEN** that stage is not re-executed and no duplicate state is written

### Requirement: Fail-closed gating

The runner SHALL stop downstream apply when a safety gate fails, and SHALL NOT
feed partial or stale stage output into dependent stages. The runner SHALL never
call `/api/combos/test`. Any stage adapter that cannot fetch, validate, persist,
or verify its required evidence SHALL return a non-success status instead of
fabricating success. A canonical stage that is not yet wired to its domain
module SHALL return a non-success `not_implemented` status and SHALL stop the run
before any dependent stage; the runner SHALL NOT provide a catch-all adapter
that returns success for unwired stages. A recoverable `partial_stale` outcome
SHALL NOT abort the run: later stages still execute, dependents simply do not
consume the stale slice, and the run reports the most severe outcome. Hard
failures — `validation_failed`, `external_dependency_failed`, `not_implemented`,
`unsafe_to_apply`, `apply_failed_rolled_back`, `rollback_failed` — still stop the
run or gate apply. Continuing past staleness SHALL NOT relax apply gates: apply
SHALL still exclude endpoints whose access/probe evidence is stale.

#### Scenario: Failed gate stops apply
- **WHEN** a safety gate (snapshot, validation, access, or probe) fails
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

#### Scenario: Stale stage does not abort the run
- **WHEN** an early stage returns `partial_stale`
- **THEN** the remaining stages still execute in order
- **AND** the run is not aborted at the stale stage

#### Scenario: Apply still excludes stale evidence
- **WHEN** the run continued past a `partial_stale` access/telemetry stage
- **THEN** apply excludes endpoints whose access/probe evidence is stale
- **AND** the applied combo only contains endpoints with fresh safe evidence

### Requirement: Matching and access stages produce real effects

The composed runtime SHALL drive the `model-matching` and `access-classification`
stages through their existing domain modules and persist their real output
through the repository. FMO SHALL NOT drive a `quota-research` stage. Each stage
SHALL report `success` only when its declared effect is observable, and SHALL
fail closed otherwise. Access status SHALL use the canonical vocabulary
`confirmed | inferred | assumed_shared | unknown`, and `unknown` SHALL NOT be
treated as free access.

#### Scenario: Matching writes endpoint bindings
- **WHEN** the `model-matching` stage runs over discovered free candidates
- **THEN** matched provider-endpoint rows are written through the repository
- **AND** an adapter returning success without writing matches fails the suite

#### Scenario: Access classification persists status
- **WHEN** the `access-classification` stage classifies an endpoint
- **THEN** its status and evidence are persisted with one of the canonical values
- **AND** an `unknown` status is never recorded as free access

#### Scenario: External payload missing fails closed
- **WHEN** a required external payload for either stage is missing or stale
- **THEN** the stage returns `external_dependency_failed` or `partial_stale`
- **AND** dependent stages do not run

### Requirement: Probe, telemetry, and quota-sync stages produce real effects

The composed runtime SHALL drive the `probing` and `telemetry-sync` stages through
their existing domain modules and persist their real output. FMO SHALL NOT drive
a `quota-sync` stage. The production probe adapter SHALL run only for
`confirmed`-free endpoints with positive delegated/free access evidence. Each
stage SHALL report `success` only when its declared effect is observable.

#### Scenario: Probe respects confirmed free access
- **WHEN** the `probing` stage runs
- **THEN** it probes only `confirmed`-free endpoints with positive access evidence

#### Scenario: Probe persists results and excludes failures
- **WHEN** the `probing` stage completes
- **THEN** probe results are persisted through the repository
- **AND** endpoints whose probe fails are excluded from downstream stages

#### Scenario: Telemetry sync writes normalized rows
- **WHEN** the `telemetry-sync` stage runs
- **THEN** normalized telemetry rows are persisted for use by scoring
- **AND** an adapter returning success without writing telemetry fails the suite

### Requirement: Account discovery runs in the pipeline and produces real effects

The composed runtime SHALL include an `account-discovery` stage that drives the
`account-discovery` domain module against the OmniRoute management API and
persists provider-account scope metadata plus independence status
(`confirmed | inferred | assumed_shared | unknown`) through the repository. The
stage SHALL run after candidate discovery and before scoring. FMO SHALL NOT
persist quota-pool membership rows. The stage SHALL report `success` only when
its declared persistence effect is observable, and SHALL fail closed
(conservative status, no `confirmed` promotion) when rate-limit availability data
is unavailable.

#### Scenario: Account discovery persists account scopes
- **WHEN** the `account-discovery` stage runs
- **THEN** account scope metadata and independence status are persisted through
  the repository
- **AND** an adapter returning success without writing account rows fails the suite

#### Scenario: Account discovery ordered before allocation inputs
- **WHEN** the canonical pipeline runs
- **THEN** `account-discovery` runs after candidate discovery and before scoring

#### Scenario: Unavailable rate-limit data stays conservative
- **WHEN** the rate-limit availability fetch fails during the stage
- **THEN** account scope metadata is still persisted
- **AND** no connection is promoted to `confirmed` independent capacity
