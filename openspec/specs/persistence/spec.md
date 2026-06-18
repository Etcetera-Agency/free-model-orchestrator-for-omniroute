# persistence Specification

## Purpose
Define the PostgreSQL repository layer used by orchestrator stages to persist
run state, domain records, idempotency keys, and immutable external snapshots.
## Requirements
### Requirement: Repository access layer

The system SHALL provide a repository layer that reads and writes orchestrator
state through typed functions per domain table in `reference/db/schema.sql`,
rather than ad-hoc SQL embedded in pipeline stages. Each pipeline stage SHALL
persist and load its state exclusively through this layer.

#### Scenario: Round-trip a provider endpoint
- **WHEN** a stage writes a provider_endpoint through the repository and another
  read loads it
- **THEN** the loaded record equals the written record including status fields

#### Scenario: Stages do not embed schema SQL
- **WHEN** a pipeline stage persists state
- **THEN** it calls a repository function and does not issue table SQL directly

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
repeating a write with unchanged inputs creates no duplicate rows.

#### Scenario: Re-run does not duplicate
- **WHEN** a stage write with an unchanged idempotency key runs twice
- **THEN** exactly one row exists for that key

### Requirement: Immutable content-hashed snapshots

Every external fetch SHALL be persisted as an immutable snapshot identified by
the content hash of its payload. Storing identical payload content twice SHALL
yield a single snapshot row.

#### Scenario: Duplicate payload is one snapshot
- **WHEN** the same external payload is stored twice
- **THEN** one content-hashed snapshot row exists and neither copy is mutated
