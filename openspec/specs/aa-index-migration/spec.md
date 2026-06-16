# aa-index-migration Specification

## Purpose
TBD - created by archiving change add-advisory-llm. Update Purpose after archive.
## Requirements
### Requirement: Version change freezes thresholds and keeps combos

On detecting a new Artificial Analysis index version the system SHALL freeze the
existing thresholds bound to the old version, stop production threshold
recalculation, and keep current combos active. It SHALL NOT silently recalculate
thresholds against the new index.

#### Scenario: New major index arrives
- GIVEN active thresholds bound to index v1 and a daily sync returns v2
- WHEN the change is detected
- THEN v1 thresholds are frozen, current combos stay active, and a migration is created

### Requirement: LLM proposal via strongest model

The system SHALL select the highest available new-`intelligence_index` model and
use an Instructor `MigrationProposal` to propose new per-role thresholds, with
percentile mapping used only as a reference signal, not as the mandatory
algorithm.

#### Scenario: Proposal generation
- GIVEN a migration is in progress and a capable model is available
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

