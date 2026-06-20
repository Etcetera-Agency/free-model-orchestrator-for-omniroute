# aa-index-migration Specification

## Purpose
TBD - created by archiving change add-advisory-llm. Update Purpose after archive.
## Requirements
### Requirement: Version change freezes thresholds and keeps combos

The system SHALL detect new Artificial Analysis index versions from authenticated
AA metadata snapshots. On detecting a new Artificial Analysis index version from
the fetched AA metadata snapshot, the system SHALL freeze the existing thresholds bound to the old
version, stop production threshold recalculation, and keep current combos
active. It SHALL NOT silently recalculate thresholds against the new index. If
the AA API key is missing, the AA fetch fails, or the response returns invalid
payload, the system SHALL keep the previous valid index version and SHALL NOT
start a migration from partial data.

#### Scenario: New major index arrives
- GIVEN active thresholds bound to index v1 and a daily AA sync returns v2
- WHEN the change is detected
- THEN v1 thresholds are frozen, current combos stay active, and a migration is created

#### Scenario: AA fetch fails
- GIVEN active thresholds bound to index v1 and the API-key authenticated AA metadata fetch fails
- WHEN daily metadata sync runs
- THEN no new index migration is created
- AND current thresholds and combos remain unchanged

#### Scenario: AA API key missing
- GIVEN active thresholds bound to index v1 and no AA API key is configured
- WHEN daily metadata sync reaches AA index detection
- THEN no new index migration is created
- AND current thresholds and combos remain unchanged

### Requirement: LLM proposal via strongest model

The system SHALL select the highest available new-`intelligence_index` model from
the fetched valid AA snapshot and use an Instructor `MigrationProposal` to
propose new per-role thresholds, with percentile mapping used only as a
reference signal, not as the mandatory algorithm.

#### Scenario: Proposal generation
- GIVEN a migration is in progress and a capable model is available in the fetched AA snapshot
- WHEN the migration agent runs
- THEN it returns a validated structured threshold proposal

### Requirement: Deterministic validation, approval and rollback

The system SHALL validate the proposal deterministically (schema, combo size,
quality, quota capacity), run a dry-run, and apply new thresholds only after
approval; it SHALL roll back on smoke-test failure. If no migration model is
available, production thresholds and combos SHALL remain unchanged.

#### Scenario: No migration model
- GIVEN no model with the new index is available
- WHEN migration is attempted
- THEN production thresholds and combos remain unchanged

#### Scenario: Smoke test fails after rollout
- GIVEN approved thresholds are rolled out and the smoke test fails
- WHEN failure is handled
- THEN the migration is rolled back to the previous thresholds

### Requirement: Migration agent runs in production via the shared runtime

The production migration capability SHALL invoke `run_migration_agent` over the
shared Instructor runtime for the `analyze`/`proposal` steps. The LLM output is
an advisory threshold proposal only; deterministic code SHALL own freeze on AA
version change, proposal validation, approval, rollout, and smoke-fail rollback.
When AA fetch fails or no migration model is available, the capability SHALL fail
closed and keep existing combos and thresholds frozen.

#### Scenario: Advisory proposal generated
- **WHEN** `aa-index analyze` runs with the runtime available
- **THEN** `run_migration_agent` produces an advisory threshold proposal
- **AND** the proposal is persisted but not auto-applied

#### Scenario: Deterministic approval and rollout
- **WHEN** an operator approves and rolls out a proposal
- **THEN** thresholds change only through the deterministic rollout path
- **AND** a smoke-test failure after rollout triggers deterministic rollback

#### Scenario: AA unavailable freezes thresholds
- **WHEN** the AA fetch fails or no migration model is available
- **THEN** thresholds and combos stay frozen and the run fails closed

