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
by the existing stage modules rather than reimplementing them.

#### Scenario: Stages run in order
- **WHEN** a full run is invoked
- **THEN** stages execute in the canonical order
- **AND** each stage records its outcome against the run

#### Scenario: Run is identified
- **WHEN** a run is started
- **THEN** a run record with a run id is persisted via the repository layer

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
call `/api/combos/test`.

#### Scenario: Failed gate stops apply
- **WHEN** a safety gate (quota, snapshot, validation, probe) fails
- **THEN** apply does not run and the run reports the failing gate

#### Scenario: Partial data not consumed
- **WHEN** a stage returns partial or stale output
- **THEN** dependent stages do not consume it and the run is marked partial/stale

#### Scenario: No combo test call
- **WHEN** the pipeline applies combos
- **THEN** `/api/combos/test` is not called

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
