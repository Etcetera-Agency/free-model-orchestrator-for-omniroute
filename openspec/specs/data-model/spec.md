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

The system SHALL use the single status set `confirmed | inferred | assumed_shared
| unknown` for quota independence and quota attribution across all tables.

#### Scenario: Independence default
- GIVEN a newly discovered provider account
- WHEN it is created
- THEN its independence status defaults to `assumed_shared` and is constrained to
  the canonical set

