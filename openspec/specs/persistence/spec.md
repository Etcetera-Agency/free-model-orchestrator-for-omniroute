# persistence Specification

## Purpose
Define the PostgreSQL repository layer used by orchestrator stages to persist
run state, domain records, idempotency keys, and immutable external snapshots.
## Requirements
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

### Requirement: Explicit transaction boundaries

The system SHALL expose an explicit transaction boundary so a stage's writes
commit atomically or leave no partial state. The connection SHALL be built from
`DATABASE_URL`.

#### Scenario: Failed write rolls back
- **WHEN** a write inside a transaction raises before commit
- **THEN** no rows from that transaction are visible to a later connection

#### Scenario: Committed write is durable
- **WHEN** a transaction commits
- **THEN** a new connection observes the written rows

### Requirement: Idempotent repository writes

The system SHALL keep repository writes idempotent on their stage idempotency
key (catalog snapshot, quota source, quota rule, probe, combo apply), so that
repeating a write with unchanged inputs creates no duplicate rows. Free registry
snapshots and provider catalog snapshots SHALL preserve their content-hash
idempotency behind repository methods.

#### Scenario: Re-run does not duplicate
- **WHEN** a stage write with an unchanged idempotency key runs twice
- **THEN** exactly one row exists for that key

#### Scenario: Discovery repository writes remain idempotent
- **WHEN** the same provider catalog or free registry payload is persisted twice
  through the repository
- **THEN** duplicate snapshot or model-definition rows are not created

### Requirement: Immutable content-hashed snapshots

Every external fetch SHALL be persisted as an immutable snapshot identified by
the content hash of its payload. Storing identical payload content twice SHALL
yield a single snapshot row.

#### Scenario: Duplicate payload is one snapshot
- **WHEN** the same external payload is stored twice
- **THEN** one content-hashed snapshot row exists and neither copy is mutated

### Requirement: External metadata persisted for downstream stages

The external-metadata-sync stage SHALL persist its fetched output — models.dev
free candidates and the Artificial Analysis snapshot — through the repository
layer so that downstream discovery and scoring read stored metadata rather than a
discarded in-memory result. A dry-run SHALL fetch and validate but persist
nothing.

#### Scenario: Sync writes metadata through the repository
- **WHEN** the metadata-sync stage runs without dry-run
- **THEN** the models.dev candidates and the AA snapshot are persisted via the
  repository layer

#### Scenario: Dry-run persists nothing
- **WHEN** the metadata-sync stage runs with dry-run
- **THEN** no external metadata is written to the database
