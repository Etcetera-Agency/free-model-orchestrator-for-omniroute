# cli-and-operations Specification

## MODIFIED Requirements

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
