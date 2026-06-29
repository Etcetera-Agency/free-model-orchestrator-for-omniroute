# persistence Specification

## Purpose
Define repository behavior for current publisher-owned state.

## Requirements

### Requirement: Repository persists current publisher state
Persistence SHALL provide repositories for runs, roles, role consumers, audit,
locks, and published generations.

#### Scenario: Committed write is durable
- **WHEN** a transaction commits
- **THEN** the row is visible to a new transaction.

#### Scenario: Failed write rolls back
- **WHEN** a transaction raises
- **THEN** rows written in that transaction are rolled back.

#### Scenario: Dry-run persists nothing
- **WHEN** dry-run is requested
- **THEN** mutating operations are skipped.

#### Scenario: Stages do not embed schema SQL
- **WHEN** stages persist state
- **THEN** they use repository methods, not table DDL.

#### Scenario: Re-run refreshes current combo snapshot recency
- **WHEN** current combo snapshots are read for profile normalization
- **THEN** recency is refreshed without creating combo ownership state.
