# aa-index-migration Specification

## MODIFIED Requirements

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
