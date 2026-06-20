# cli-and-operations Specification

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
SHALL NOT return an unconditional success. The `discover-accounts` command SHALL
execute the `account-discovery` stage (connection/rate-limit fetch and
quota-pool grouping), NOT the free-candidate-discovery stage. `apply` and
`rollback` SHALL run through the runner's fail-closed gating. Diagnostics SHALL
read persisted state.

#### Scenario: Stage command invokes its stage
- **WHEN** a per-stage command such as `allocate` or `scan-providers` runs
- **THEN** the runner executes the matching pipeline stage
- **AND** the command exit code reflects that stage's outcome, not an
  unconditional success

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

#### Scenario: Discover-accounts command uses account discovery
- **WHEN** an operator runs `discover-accounts`
- **THEN** the runner executes the `account-discovery` stage, fetching
  connections and rate-limit availability and grouping quota pools
- **AND** pool membership and independence status are persisted through the
  production persistence path
- **AND** the command does not run the free-candidate-discovery stage

#### Scenario: Apply surfaces gating outcomes
- **WHEN** `apply` runs and a safety gate fails
- **THEN** the command exits with 5 (unsafe), 6 (applied then rolled back) or
  7 (rollback failed) according to the failure
- **AND** nothing is changed when the outcome is unsafe

#### Scenario: Explain an endpoint
- **WHEN** `explain-endpoint` runs for an endpoint id
- **THEN** it reads persisted state and prints why the endpoint was
  selected/rejected and its real score components
