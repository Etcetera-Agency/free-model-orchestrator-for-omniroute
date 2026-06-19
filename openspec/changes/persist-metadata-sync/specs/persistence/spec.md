## ADDED Requirements

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
