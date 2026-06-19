## MODIFIED Requirements

### Requirement: Registry snapshot persistence

The system SHALL persist free provider registry sync results through repository
methods. The persisted state SHALL include the free-model payload hash, ranking
payload hashes, raw JSON, drift/errors, and free model definitions for all
non-web-cookie entries.

#### Scenario: Registry outcome is persisted
- **WHEN** free registry sync fetches free-model and ranking payloads
- **THEN** the registry snapshot is stored through the repository
- **AND** each non-web-cookie free model definition is upserted through the
  repository with source snapshot id

#### Scenario: Registry writer does not own SQL writes
- **WHEN** registry sync persists production state
- **THEN** it uses repository methods within an explicit transaction
- **AND** `src/fmo/registry.py` does not embed table SQL for those production
  writes
