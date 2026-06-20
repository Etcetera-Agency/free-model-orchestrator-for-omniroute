# cli-and-operations Specification

## Purpose
Define operator command behavior, diagnostics, dry-run guarantees, and
deterministic exit codes for Free Model Orchestrator CLI operations.
## Requirements
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

#### Scenario: Apply surfaces gating outcomes
- **WHEN** `apply` runs and a safety gate fails
- **THEN** the command exits with 5 (unsafe), 6 (applied then rolled back) or
  7 (rollback failed) according to the failure
- **AND** nothing is changed when the outcome is unsafe

#### Scenario: Explain an endpoint
- **WHEN** `explain-endpoint` runs for an endpoint id
- **THEN** it reads persisted state and prints why the endpoint was
  selected/rejected and its real score components

### Requirement: Deterministic exit codes

The system SHALL return exit codes: 0 success; 2 partial/stale data; 3 validation
failed; 4 external dependency failed; 5 unsafe to apply; 6 apply failed and
rolled back; 7 rollback failed.

#### Scenario: Unsafe apply
- GIVEN apply preconditions are not met
- WHEN `apply` runs
- THEN it exits with code 5 and changes nothing

### Requirement: Local dry-run without combo test

The system SHALL perform local dry-run validation of the final combo without
upstream model calls and SHALL never call `/api/combos/test`. On `--dry-run` the
CLI SHALL execute the selected pipeline stage(s) in read-only mode rather than
returning an unconditional success: each stage SHALL run its validation path and
report its real outcome and exit code, while making no OmniRoute mutation. The
`apply` command on `--dry-run` SHALL run its precondition/validation path and
report the would-be outcome (including `unsafe_to_apply`) without mutating any
combo.

#### Scenario: Dry-run validation
- GIVEN `--dry-run`
- WHEN allocation completes
- THEN the combo is validated locally and `/api/combos/test` is not called

#### Scenario: Dry-run runs the stage, not an unconditional success
- GIVEN `diff --dry-run` or `full --dry-run`
- WHEN the command runs
- THEN the selected stage(s) execute read-only and the exit code reflects the
  real stage outcome
- AND no OmniRoute mutation call is made

#### Scenario: Apply dry-run previews without mutating
- GIVEN `apply --dry-run` and a failing safety gate
- WHEN the command runs
- THEN the precondition/validation path runs and reports `unsafe_to_apply`
- AND no combo is mutated and `/api/combos/test` is not called

### Requirement: CLI command surface

The CLI SHALL expose operations for metadata sync and full orchestration. The
`sync-metadata` command SHALL fetch both models.dev and Artificial Analysis
metadata using configured URLs/defaults, require a configured Artificial Analysis
API key for AA requests, report structured external dependency failures,
redact API keys from command output, and support `--dry-run` without applying database mutations. The
`full` command SHALL run metadata sync before discovery, matching, scoring,
allocation, diff, and apply.

#### Scenario: sync-metadata fetches external metadata
- GIVEN valid external metadata endpoints
- WHEN `sync-metadata` runs
- THEN models.dev catalog sync runs
- AND Artificial Analysis metadata sync runs with x-api-key authentication

#### Scenario: sync-metadata missing AA API key
- GIVEN no Artificial Analysis API key is configured
- WHEN `sync-metadata` runs
- THEN the command reports `aa_api_key_required`
- AND the command output contains no secret value

#### Scenario: sync-metadata dry run
- GIVEN `sync-metadata --dry-run`
- WHEN the command runs
- THEN external metadata requests may be validated through injected clients
- AND no database mutation or apply operation is performed

#### Scenario: full command order
- GIVEN the `full` command runs
- WHEN orchestration starts
- THEN metadata sync completes before candidate discovery and scoring

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

