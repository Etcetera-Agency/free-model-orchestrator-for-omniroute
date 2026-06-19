## MODIFIED Requirements

### Requirement: Stage command invokes its stage

Each CLI stage command SHALL invoke the matching production stage through the
composed runtime and return that stage's real exit code. `sync-free-registry`
SHALL invoke the free provider registry sync path. `scan-providers` SHALL invoke
the OmniRoute provider/catalog scanner path. Commands SHALL NOT be mapped to an
unrelated placeholder or metadata-only stage.

#### Scenario: Stage command invokes its stage
- **WHEN** an operator runs a per-stage CLI command
- **THEN** the command dispatches to the matching production stage
- **AND** the stage invokes its domain module or adapter
- **AND** the CLI exit code reflects that stage's outcome

#### Scenario: Registry command uses registry sync
- **WHEN** an operator runs `sync-free-registry`
- **THEN** the free provider registry sync client fetches free-model and ranking
  payloads
- **AND** the registry outcome is persisted through the production persistence
  path

#### Scenario: Provider scan command uses catalog scanner
- **WHEN** an operator runs `scan-providers`
- **THEN** the OmniRoute provider/account catalog scanner fetches provider and
  model payloads
- **AND** provider accounts, catalog snapshots, and discovered endpoints are
  written through the production persistence path
