# data-model Specification

## Purpose
Define the database entities FMO still owns after provider/model orchestration is delegated to OmniRoute.

## Requirements

### Requirement: FMO-owned data model is publisher-only
The schema SHALL keep run, role, consumer, demand, audit, lock and published
generation state. It SHALL NOT keep provider/model/endpoint/probe/scoring/apply
ownership tables.

#### Scenario: Fresh install
- **WHEN** `reference/db/schema.sql` is applied to a fresh database
- **THEN** current publisher tables are created.

#### Scenario: Role reference type
- **WHEN** role-owned records are persisted
- **THEN** they reference the role id as text.

#### Scenario: Repository is the only writer
- **WHEN** domain state is stored
- **THEN** writes go through repository methods.

#### Scenario: Auxiliary consumer type persists
- **WHEN** Hermes reports an auxiliary role consumer
- **THEN** `role_consumers.consumer_type='auxiliary'` is accepted.

#### Scenario: Migration keeps existing databases compatible
- **WHEN** an older database is upgraded
- **THEN** ordered migrations remove retired tables without breaking current tables.
