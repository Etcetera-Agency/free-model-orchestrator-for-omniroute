# runtime-bootstrap Specification

## Purpose
Define environment-driven service startup, validation, and entrypoint behavior
before any orchestrator pipeline stage executes.
## Requirements
### Requirement: Environment-driven startup

The system SHALL build `StartupConfig` from environment variables
(`OMNIROUTE_URL`, `DATABASE_URL`, `HERMES_INVENTORY_MODE`,
`HERMES_INVENTORY_CRON`, and the mode-specific fields) and SHALL run startup
validation — static config plus an OmniRoute health check — before any pipeline
stage executes. Validation failure SHALL map to exit code 3.

#### Scenario: Invalid environment fails before running
- **WHEN** a required environment value is missing or invalid
- **THEN** startup validation fails with exit code 3 and no stage runs

#### Scenario: Health check precedes the pipeline
- **WHEN** startup validation passes
- **THEN** the OmniRoute health check has run before the first pipeline stage

### Requirement: Real service entrypoint

The package entrypoint SHALL parse the actual process arguments and derive apply
preconditions from startup validation, not from a hardcoded value. The
entrypoint SHALL bootstrap configuration and then dispatch to the CLI or runner.

#### Scenario: Entrypoint uses real arguments
- **WHEN** the entrypoint is invoked with command-line arguments
- **THEN** it parses those arguments and dispatches accordingly
- **AND** apply preconditions reflect actual startup validation state

### Requirement: Default production pipeline wiring

The package entrypoint SHALL supply, as production defaults, a `PipelineRunner`
composed from the existing stage modules and a repository-backed diagnostics
reader, so that per-stage CLI commands execute their stage and `explain-*`
commands read persisted state without any injected test seam. The composition
SHALL build the canonical ordered stage list driven by the stage modules rather
than reimplementing stage logic.

#### Scenario: Production dispatch executes a real stage
- **WHEN** a per-stage command runs through the package entrypoint with no
  injected pipeline runner
- **THEN** the composed runner executes the matching pipeline stage
- **AND** the command returns that stage's real outcome, not an unconditional
  success

#### Scenario: Diagnostics read persisted state by default
- **WHEN** `explain-endpoint` or `explain-role` runs through the package
  entrypoint with no injected diagnostics reader
- **THEN** the command reads persisted state through the repository layer and
  returns non-null output
