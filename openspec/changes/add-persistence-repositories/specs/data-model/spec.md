## ADDED Requirements

### Requirement: State access through the repository layer

The system SHALL access all persisted orchestrator state through the repository
layer (see capability `persistence`), so that the schema in
`reference/db/schema.sql` is the only place table structure is defined and no
stage duplicates table DDL or embeds raw table SQL.

#### Scenario: Repository is the only writer
- **WHEN** any stage mutates persisted state
- **THEN** the mutation goes through a repository function bound to a table in
  `reference/db/schema.sql`
