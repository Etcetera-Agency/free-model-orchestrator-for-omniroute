## MODIFIED Requirements

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
run or gate apply. Continuing past staleness SHALL NOT relax any capacity gate:
apply SHALL still exclude endpoints whose quota/probe evidence is stale.

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

#### Scenario: Stale stage does not abort the run
- **WHEN** an early stage returns `partial_stale`
- **THEN** the remaining stages still execute in order
- **AND** the run is not aborted at the stale stage

#### Scenario: Apply still excludes stale evidence
- **WHEN** the run continued past a `partial_stale` quota/telemetry stage
- **THEN** apply excludes endpoints whose quota/probe evidence is stale
- **AND** the applied combo only contains endpoints with fresh safe evidence

### Requirement: Run outcome exit codes

The runner SHALL map a run outcome to a deterministic exit code: 0 success;
2 partial/stale; 3 validation failed; 4 external dependency failed; 5 unsafe to
apply; 6 apply failed and rolled back; 7 rollback failed. When multiple stages
fail, the runner SHALL report the most severe outcome. A run whose only
non-success outcome is `partial_stale` SHALL exit 2 even though all later stages
ran.

#### Scenario: Unsafe apply outcome
- **WHEN** apply preconditions are not met
- **THEN** the run exits with code 5 and changes nothing

#### Scenario: External dependency failure outcome
- **WHEN** a required external fetch fails
- **THEN** the run exits with code 4

#### Scenario: Stale stage yields exit 2 while later stages run
- **WHEN** a stage returns `partial_stale` and no later stage fails harder
- **THEN** every later stage still executes
- **AND** the run exits with code 2
