# pipeline-orchestration Specification

## Purpose
Define the deterministic daily pipeline runner that records orchestrator runs,
executes ordered stages, skips unchanged idempotent work, fails closed on unsafe
state, and maps outcomes to operator exit codes.
## Requirements
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

### Requirement: Idempotent stage skipping

The runner SHALL skip a stage whose idempotency key (catalog snapshot, quota
source, quota rule, probe, combo apply) matches a prior successful result, so a
re-run with unchanged inputs applies no combo change and re-runs no unchanged
probe.

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

### Requirement: Run outcome exit codes

The runner SHALL map a run outcome to a deterministic exit code: 0 success;
2 partial/stale; 3 validation failed; 4 external dependency failed; 5 unsafe to
apply; 6 apply failed and rolled back; 7 rollback failed. When multiple stages
fail, the runner SHALL report the most severe outcome.

#### Scenario: Unsafe apply outcome
- **WHEN** apply preconditions are not met
- **THEN** the run exits with code 5 and changes nothing

#### Scenario: External dependency failure outcome
- **WHEN** a required external fetch fails
- **THEN** the run exits with code 4

### Requirement: Matching and access stages produce real effects

The composed runtime SHALL drive the `model-matching`, `quota-research`, and
`access-classification` stages through their existing domain modules and persist
their real output through the repository. Each stage SHALL report `success` only
when its declared effect is observable, and SHALL fail closed otherwise. Access
status SHALL use the canonical vocabulary `confirmed | inferred | assumed_shared
| unknown`, and `unknown` SHALL NOT be treated as free access.

#### Scenario: Matching writes endpoint bindings
- **WHEN** the `model-matching` stage runs over discovered free candidates
- **THEN** matched provider-endpoint rows are written through the repository
- **AND** an adapter returning success without writing matches fails the suite

#### Scenario: Quota research persists capped rules
- **WHEN** the `quota-research` stage extracts quota bounds
- **THEN** content-hashed quota snapshots and rules are persisted
- **AND** summary-sourced rules are capped by `summary_confidence_cap`

#### Scenario: Access classification persists status
- **WHEN** the `access-classification` stage classifies an endpoint
- **THEN** its status and evidence are persisted with one of the canonical values
- **AND** an `unknown` status is never recorded as free access

#### Scenario: External payload missing fails closed
- **WHEN** a required external payload for any of these stages is missing or stale
- **THEN** the stage returns `external_dependency_failed` or `partial_stale`
- **AND** dependent stages do not run

### Requirement: Probe, telemetry, and quota-sync stages produce real effects

The composed runtime SHALL drive the `probing`, `telemetry-sync`, and
`quota-sync` stages through their existing domain modules and persist their real
output. The production probe adapter SHALL run only for `confirmed`-free
endpoints with reserved capacity and SHALL never exceed confirmed free capacity.
Each stage SHALL report `success` only when its declared effect is observable.

#### Scenario: Probe respects confirmed free capacity
- **WHEN** the `probing` stage runs
- **THEN** it probes only `confirmed`-free endpoints with reserved capacity
- **AND** no probe request exceeds confirmed free capacity

#### Scenario: Probe persists results and excludes failures
- **WHEN** the `probing` stage completes
- **THEN** probe results are persisted through the repository
- **AND** endpoints whose probe fails are excluded from downstream stages

#### Scenario: Telemetry sync writes normalized rows
- **WHEN** the `telemetry-sync` stage runs
- **THEN** normalized telemetry rows are persisted for use by scoring
- **AND** an adapter returning success without writing telemetry fails the suite

#### Scenario: Quota sync writes remaining-quota state
- **WHEN** the `quota-sync` stage runs
- **THEN** synced remaining-quota state is persisted with correct attribution
- **AND** an adapter returning success without writing quota state fails the suite

### Requirement: Scoring, allocation, and diff stages produce real effects

The composed runtime SHALL drive the `role-scoring`, `allocation`, and `diff`
stages through their existing domain modules and persist their real output. The
`allocation` stage SHALL apply global allocation across all roles, heavy-role
separation, the oversubscription gate, one priority combo per role, and
deterministic stable ordering, with no paid fallback in degraded modes. The
`diff` stage SHALL compute the minimal change against current OmniRoute state
without mutating OmniRoute. Each stage SHALL report `success` only when its
declared effect is observable.

#### Scenario: Scoring persists per-role scores
- **WHEN** the `role-scoring` stage runs
- **THEN** per-role endpoint scores are persisted through the repository
- **AND** an adapter returning success without writing scores fails the suite

#### Scenario: Allocation persists one combo plan per role
- **WHEN** the `allocation` stage runs
- **THEN** `allocation_plans` rows are persisted with targets and constraint report
- **AND** each role receives exactly one priority combo with stable ordering

#### Scenario: Oversubscription gate blocks zero-capacity pool
- **WHEN** allocation encounters a pool with zero confirmed-free capacity
- **THEN** the role is degraded with no paid fallback
- **AND** the constraint report records the blocked pool

#### Scenario: Diff is computed without mutating OmniRoute
- **WHEN** the `diff` stage runs
- **THEN** the minimal change against current OmniRoute state is persisted
- **AND** no OmniRoute mutation call is made during diff

### Requirement: Apply and audit stages produce real effects

The composed runtime SHALL drive the `apply` and `audit` stages through their
existing domain modules. The production `apply` stage SHALL evaluate
repository-backed preconditions, apply the minimal diff transactionally to only
`fmo-` combos, run a real combo smoke test, and roll back on failure. The CLI
`combo_test_called` signal SHALL reflect whether the real smoke test ran and
SHALL NOT be hardcoded. The `audit` stage SHALL persist audit records and
snapshots. Outcomes SHALL map to exit codes `unsafe_to_apply` (5),
`apply_failed_rolled_back` (6), and `rollback_failed` (7).

#### Scenario: Production apply runs the real smoke test
- **WHEN** the `apply` stage applies a combo diff
- **THEN** the applier and a real transactional smoke test are invoked
- **AND** the CLI reports `combo_test_called` as true from the real signal
- **AND** an adapter returning success without applying or smoke-testing fails the suite

#### Scenario: Failing guard blocks apply
- **WHEN** a repository-backed apply precondition fails
- **THEN** the run returns `unsafe_to_apply` and OmniRoute is not mutated

#### Scenario: Smoke failure rolls back
- **WHEN** the apply smoke test fails
- **THEN** the change is rolled back and the run returns `apply_failed_rolled_back`
- **AND** a failed rollback returns `rollback_failed`

#### Scenario: Audit persists records
- **WHEN** the `audit` stage runs after apply
- **THEN** audit records and snapshots are persisted through the repository
- **AND** an adapter returning success without writing audit records fails the suite

### Requirement: Hermes inventory feeds the pipeline before allocation

The canonical stage order SHALL include `hermes-inventory` ahead of
`role-scoring`, and downstream demand SHALL be derived from the gathered Hermes
inventory rather than only static `expected_load`. A schedule change in Hermes
SHALL trigger a forecast-input refresh on the next run.

#### Scenario: Inventory precedes scoring
- **WHEN** a `full` run executes
- **THEN** `hermes-inventory` runs before `role-scoring`
- **AND** allocation demand reflects the gathered Hermes cadence

#### Scenario: Schedule change refreshes forecast inputs
- **WHEN** a Hermes schedule changes between runs
- **THEN** the next run refreshes the affected forecast inputs

### Requirement: Forecast and lifecycle run before allocation

The pipeline SHALL run role-lifecycle reconciliation and demand forecasting
before allocation so that allocation operates over a reconciled role set with
forecast-derived demand. These steps SHALL be deterministic and SHALL produce
observable persisted effects.

#### Scenario: Reconcile and forecast precede allocation
- **WHEN** a `full` run executes
- **THEN** role-lifecycle reconcile and demand forecast complete before allocation
- **AND** allocation consumes the reconciled roles and forecast demand

### Requirement: Scoring stage applies context and quality hard filters

The composed runtime's `role-scoring` stage SHALL apply the
context-window-eligibility and quality-gate hard filters as part of its
production eligibility path before persisting scores. Endpoints below a role's
context-window minimum (effective context = min of known sources, unknown
excluded unless the role overrides) and endpoints failing or unverifiable
against the role's optional quality gate (unless the role allows unverified)
SHALL NOT receive a persisted score for that role. On an Artificial Analysis
index-version mismatch the gate SHALL be treated as `needs_recalibration`: no new
plan is applied for that role and the current combo is kept. The persisted
rejection reason SHALL distinguish context and quality exclusions.

#### Scenario: Scoring stage drops below-context endpoint
- **WHEN** the `role-scoring` stage runs and an endpoint is below the role
  context minimum
- **THEN** no score row is persisted for that endpoint/role
- **AND** the persisted rejection reason identifies the context filter

#### Scenario: Scoring stage drops below-gate endpoint
- **WHEN** the `role-scoring` stage runs and an endpoint is below the role
  quality gate
- **THEN** no score row is persisted for that endpoint/role
- **AND** the persisted rejection reason identifies the quality gate

#### Scenario: Index-version mismatch keeps current combo
- **WHEN** the `role-scoring` stage runs against a quality gate bound to a stale
  index version
- **THEN** the gate is marked `needs_recalibration`
- **AND** no new allocation plan is applied for that role

