# runtime-bootstrap Specification

## Purpose
Define startup validation before current publisher runtime dispatch.

## Requirements

### Requirement: Bootstrap validates before dispatch
Startup SHALL validate environment, health and inventory configuration before
running publisher stages.

#### Scenario: Invalid environment fails before running
- **WHEN** required startup configuration is invalid
- **THEN** dispatch is not called and exit code 3 is returned.

#### Scenario: Health check precedes the pipeline
- **WHEN** bootstrap starts
- **THEN** the health check runs before dispatch.

#### Scenario: Entrypoint uses real arguments
- **WHEN** `main` is called with arguments
- **THEN** those arguments are dispatched unchanged after validation.

#### Scenario: Production dispatch executes a real stage
- **WHEN** no injected runner is supplied
- **THEN** production composition executes the requested current stage.

#### Scenario: Diagnostics read persisted state by default
- **WHEN** `explain-role` is used without an injected reader
- **THEN** persisted role diagnostics are read.
