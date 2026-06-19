## MODIFIED Requirements

### Requirement: Snapshot storage

The system SHALL persist provider catalog snapshots with a stable content hash,
fetch status, model count, and raw payload through repository methods. A repeated
successful snapshot with identical content SHALL be detected as unchanged.

#### Scenario: Successful catalog snapshot is stored
- **WHEN** an OmniRoute provider catalog fetch succeeds
- **THEN** the snapshot is stored through the repository with hash, raw payload,
  model count, and success status

#### Scenario: Unchanged catalog is detected
- **WHEN** the latest successful catalog hash matches the newly fetched payload
- **THEN** the scan result marks the catalog unchanged

#### Scenario: Scanner does not own SQL writes
- **WHEN** provider scanner persists provider, account, catalog, or endpoint
  state
- **THEN** it uses repository methods within an explicit transaction
- **AND** `src/fmo/scanner.py` does not embed table SQL for those production
  writes
