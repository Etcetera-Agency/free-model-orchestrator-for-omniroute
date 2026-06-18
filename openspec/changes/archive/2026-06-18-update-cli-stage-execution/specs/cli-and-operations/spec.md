## MODIFIED Requirements

### Requirement: Operator command set

The system SHALL provide per-stage commands (sync-free-registry,
discover-accounts, scan-providers, research-quotas, classify-access,
sync-metadata, match-models, probe-models, sync-telemetry, sync-quotas,
score-roles, allocate, diff, apply, rollback, full), the `aa-index` migration
subcommands, and diagnostics (`explain-endpoint`, `explain-role`, `show-*`).
Common flags include `--dry-run`, `--provider`, `--account`, `--endpoint`,
`--role`, `--run-id`, `--force`, `--json`, `--verbose`.

Each per-stage command SHALL execute its corresponding pipeline stage through the
pipeline runner and return that stage's real outcome and exit code; commands
SHALL NOT return an unconditional success. `apply` and `rollback` SHALL run
through the runner's fail-closed gating. Diagnostics SHALL read persisted state.

#### Scenario: Stage command invokes its stage
- **WHEN** a per-stage command such as `allocate` or `scan-providers` runs
- **THEN** the runner executes the matching pipeline stage
- **AND** the command exit code reflects that stage's outcome, not an
  unconditional success

#### Scenario: Apply surfaces gating outcomes
- **WHEN** `apply` runs and a safety gate fails
- **THEN** the command exits with 5 (unsafe), 6 (applied then rolled back) or
  7 (rollback failed) according to the failure
- **AND** nothing is changed when the outcome is unsafe

#### Scenario: Explain an endpoint
- **WHEN** `explain-endpoint` runs for an endpoint id
- **THEN** it reads persisted state and prints why the endpoint was
  selected/rejected and its real score components
