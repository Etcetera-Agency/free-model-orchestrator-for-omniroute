# pipeline-orchestration Specification

## Purpose
Define deterministic publisher pipeline execution and outcome recording.

## Requirements

### Requirement: Publisher pipeline runs deterministic stages
The pipeline SHALL run current publisher stages in order and record stage
outcomes with idempotency keys.

#### Scenario: Run is identified
- **WHEN** a pipeline run starts
- **THEN** a `sync_runs` record identifies it.

#### Scenario: Stages run in order
- **WHEN** multiple stages are configured
- **THEN** they execute in configured order.

#### Scenario: Unchanged re-run skips work
- **WHEN** a previous successful stage has the same idempotency key
- **THEN** the stage is skipped.

#### Scenario: Partial data not consumed
- **WHEN** one stage returns partial stale data
- **THEN** the run reports partial stale.

#### Scenario: Stale stage does not abort the run
- **WHEN** a stage returns `partial_stale`
- **THEN** later stages still run.

#### Scenario: Stale stage yields exit 2 while later stages run
- **WHEN** a partial stale stage is followed by success
- **THEN** the pipeline exit code is 2.

#### Scenario: External dependency failure outcome
- **WHEN** a stage fails on an external dependency
- **THEN** the pipeline maps it to exit code 4.

#### Scenario: Stage success requires a real effect
- **WHEN** a successful stage omits an effect declaration
- **THEN** the effect harness fails.

#### Scenario: Audit persists records
- **WHEN** publish/audit stages mutate repository state
- **THEN** audit records are persisted.
