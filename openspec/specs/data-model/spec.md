# data-model Specification

## Purpose
TBD - created by archiving change add-foundation. Update Purpose after archive.
## Requirements
### Requirement: PostgreSQL is the single store

The system SHALL persist all orchestrator state in PostgreSQL using
`reference/db/schema.sql`. A fresh install SHALL apply that consolidated schema;
an existing database SHALL be upgraded with the ordered scripts in
`reference/db/migrations/`.

#### Scenario: Fresh install
- GIVEN an empty PostgreSQL database
- WHEN `schema.sql` is applied
- THEN the full current-state schema is created with no post-hoc column patches

### Requirement: Roles are keyed by text id

The system SHALL key the `roles` table by a text id, and every role reference
(scores, plans, budgets, consumers, lifecycle, thresholds) SHALL use a matching
text foreign key.

#### Scenario: Role reference type
- GIVEN a table that references a role
- WHEN the schema is created
- THEN its `role_id` column is `text` and the foreign key resolves to `roles(id)`

### Requirement: Canonical status vocabulary

The system SHALL enforce combo state transitions through the allowed transition
set. It SHALL reject direct snapshot-to-commit, applied-to-commit without smoke,
and any backward transition.

#### Scenario: Snapshot directly committed
- GIVEN a combo is in `SNAPSHOT_SAVED`
- WHEN transition to `COMMITTED` is requested
- THEN the transition is rejected

#### Scenario: Applied directly committed
- GIVEN a combo is in `APPLIED`
- WHEN transition to `COMMITTED` is requested
- THEN the transition is rejected

#### Scenario: Backward combo transition
- GIVEN a combo is in any later state
- WHEN transition to an earlier state is requested
- THEN the transition is rejected

### Requirement: State access through the repository layer

The system SHALL access all persisted orchestrator state through the repository
layer (see capability `persistence`), so that the schema in
`reference/db/schema.sql` is the only place table structure is defined and no
stage duplicates table DDL or embeds raw table SQL.

#### Scenario: Repository is the only writer
- **WHEN** any stage mutates persisted state
- **THEN** the mutation goes through a repository function bound to a table in
  `reference/db/schema.sql`

### Requirement: Role carries a quality band upper bound

The `roles` table SHALL carry `maximum_quality_metric` and
`maximum_quality_value` beside the existing `minimum_quality_metric` /
`minimum_quality_value`, with a metric check matching the minimum's
(`intelligence_index | coding_index | agentic_index`). Together they express the
role's quality band `[min, max]`. The columns are nullable; a NULL maximum means
no upper bound (min-only behavior).

#### Scenario: Role carries a maximum quality bound
- GIVEN a fresh schema install (or applied migration)
- WHEN a role is written with a band
- THEN `maximum_quality_metric` / `maximum_quality_value` persist and round-trip
- AND a role written without an upper bound stores NULL for the maximum

### Requirement: Role consumers include auxiliary Hermes slots

The `role_consumers.consumer_type` constraint SHALL accept every Hermes consumer
surface persisted by inventory: `agent_profile`, `cron_job`, `webhook`,
`service`, and `auxiliary`. Fresh installs SHALL include that vocabulary in
`reference/db/schema.sql`; existing databases SHALL get the same vocabulary
through an ordered migration.

#### Scenario: Auxiliary consumer type persists
- GIVEN Hermes inventory emits an auxiliary slot consumer
- WHEN the consumer is persisted to `role_consumers`
- THEN `consumer_type = 'auxiliary'` is accepted by the database constraint

#### Scenario: Migration keeps existing databases compatible
- GIVEN an existing database created before auxiliary consumers were added
- WHEN the ordered migrations are applied
- THEN the `role_consumers_consumer_type_check` constraint accepts `auxiliary`
- AND the previous consumer types remain valid
