# cli-and-operations Specification

## ADDED Requirements

### Requirement: Operator command set

The system SHALL provide per-stage commands (sync-free-registry,
discover-accounts, scan-providers, research-quotas, classify-access,
sync-metadata, match-models, probe-models, sync-telemetry, sync-quotas,
score-roles, allocate, diff, apply, rollback, full), the `aa-index` migration
subcommands, and diagnostics (`explain-endpoint`, `explain-role`, `show-*`).
Common flags include `--dry-run`, `--provider`, `--account`, `--endpoint`,
`--role`, `--run-id`, `--force`, `--json`, `--verbose`.

#### Scenario: Explain an endpoint
- GIVEN an endpoint id
- WHEN `explain-endpoint` runs
- THEN it prints why the endpoint was selected/rejected and its score components

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
upstream model calls and SHALL never call `/api/combos/test` automatically.

#### Scenario: Dry-run validation
- GIVEN `--dry-run`
- WHEN allocation completes
- THEN the combo is validated locally and `/api/combos/test` is not called
