## MODIFIED Requirements

### Requirement: Default production pipeline wiring

The package entrypoint SHALL supply, as production defaults, a `PipelineRunner`
composed from the existing stage modules and a repository-backed diagnostics
reader, so that per-stage CLI commands execute their stage and `explain-*`
commands read persisted state without any injected test seam. The composition
SHALL build the canonical ordered stage list driven by the stage modules rather
than reimplementing stage logic. No production stage MAY return unconditional
success without invoking the domain module or adapter responsible for that
stage.

#### Scenario: Production dispatch executes a real stage
- **WHEN** a per-stage command runs through the package entrypoint with no
  injected pipeline runner
- **THEN** the composed runner executes the matching pipeline stage
- **AND** the stage invokes its domain module or adapter
- **AND** the command returns that stage's real outcome, not an unconditional
  success

#### Scenario: Diagnostics read persisted state by default
- **WHEN** `explain-endpoint` or `explain-role` runs through the package
  entrypoint with no injected diagnostics reader
- **THEN** the command reads persisted state through the repository layer and
  returns non-null output

#### Scenario: Placeholder stage rejected
- **WHEN** the canonical production stage list is built
- **THEN** every stage except explicit diagnostics-free dry-run validation is
  backed by a domain adapter
- **AND** no stage named in the canonical list is implemented by a helper that
  only returns `StageResult(status="success")`
