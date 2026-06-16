# provider-scanner Specification

## ADDED Requirements

### Requirement: Daily catalog scan and snapshot

The system SHALL fetch every registered provider's catalog once per daily batch
via `/api/providers`, `/api/providers/{id}` and `/api/providers/{id}/models`,
store an immutable `provider_catalog_snapshots` row keyed by `catalog_hash`, and
skip diffing when the hash matches the last successful snapshot. Credentials
SHALL NOT be copied.

#### Scenario: Unchanged catalog
- GIVEN a provider catalog whose hash equals the last successful snapshot
- WHEN the scanner runs
- THEN no diff is computed for that provider

### Requirement: Catalog diff and endpoint upsert

The system SHALL diff model id, name, type, flags, pricing, capabilities and
visibility, emit the corresponding `provider_model_*` events, and upsert
endpoints keyed by (provider_account_id, provider_model_id, model_type). A new
endpoint SHALL start `lifecycle_status = discovered`, `access_status =
access_pending`, `probe_status = not_run`.

#### Scenario: New model discovered
- GIVEN a model present in the catalog but not in the database
- WHEN the diff runs
- THEN an endpoint is created in `discovered` / `access_pending` / `not_run`

### Requirement: Candidate prioritization

The system SHALL classify scanned models into group A (exact models.dev
zero-cost/free candidate), group B (provider free/free-tier flag), and group C
(others). A and B go to access classification (B also to quota research); C is
processed only if previously active free, covered by a provider quota rule, or
manually overridden.

#### Scenario: Non-candidate model
- GIVEN a group-C model with no prior free status, rule, or override
- WHEN prioritization runs
- THEN it is not sent for classification

### Requirement: False-removal protection

The system SHALL mark a model `removed` (not delete it) only after two
consecutive successful catalog fetches without it, at least 5 minutes apart. If a
provider fetch errors, missing models SHALL NOT be marked removed.

#### Scenario: Fetch error
- GIVEN a provider catalog fetch fails
- WHEN models appear missing in that failed fetch
- THEN none of them are marked removed
