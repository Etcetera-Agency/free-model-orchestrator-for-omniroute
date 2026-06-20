## ADDED Requirements

### Requirement: aa-index subcommands are dispatched

`run_cli` SHALL dispatch every `aa-index` subcommand (`status`, `analyze`,
`proposal`, `approve`, `reject`, `rollout`, `rollback`) to the migration
capability through an injected handler. No `aa-index` subcommand SHALL fall
through to the default success result, and each SHALL return the documented exit
code for its outcome.

#### Scenario: aa-index subcommand routes to the handler
- **WHEN** `aa-index analyze` is invoked
- **THEN** the migration handler is called for the `analyze` step
- **AND** the command does not return the default no-op success result

#### Scenario: aa-index failure maps to an exit code
- **WHEN** an `aa-index` subcommand fails its external dependency or validation
- **THEN** the documented exit code is returned
- **AND** no `fmo-` combos are mutated
