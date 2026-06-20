## MODIFIED Requirements

### Requirement: Repository access layer

The system SHALL provide a repository layer that reads and writes orchestrator
state through typed functions per domain table in `reference/db/schema.sql`,
rather than ad-hoc SQL embedded in pipeline stages. Each pipeline stage SHALL
persist and load its state exclusively through this layer. Provider discovery,
catalog snapshot storage, free registry snapshot storage, and free model
definition upserts SHALL NOT open their own production write connections or
embed schema SQL outside repository classes.

#### Scenario: Round-trip a provider endpoint
- **WHEN** a stage writes a provider_endpoint through the repository and another
  read loads it
- **THEN** the loaded record equals the written record including status fields

#### Scenario: Stages do not embed schema SQL
- **WHEN** a pipeline stage persists state
- **THEN** it calls a repository function and does not issue table SQL directly

#### Scenario: Discovery writers use repository
- **WHEN** provider scanner or free registry sync persists production state
- **THEN** scanner and registry modules call repository methods
- **AND** table SQL for those writes exists only in repository classes

### Requirement: Idempotent repository writes

The system SHALL keep repository writes idempotent on their stage idempotency
key (catalog snapshot, quota source, quota rule, probe, combo apply), so that
repeating a write with unchanged inputs creates no duplicate rows. Free registry
snapshots and provider catalog snapshots SHALL preserve their existing
content-hash idempotency when moved behind repository methods.

#### Scenario: Re-run does not duplicate
- **WHEN** a stage write with an unchanged idempotency key runs twice
- **THEN** exactly one row exists for that key

#### Scenario: Discovery repository writes remain idempotent
- **WHEN** the same provider catalog or free registry payload is persisted twice
  through the repository
- **THEN** duplicate snapshot or model-definition rows are not created
