# provider-scanner Specification

## Purpose
TBD - created by archiving change add-discovery. Update Purpose after archive.
## Requirements
### Requirement: Daily catalog scan and snapshot

The system SHALL use only successful snapshots as the previous successful
snapshot for unchanged detection.

#### Scenario: Failed snapshot not previous
- GIVEN the latest stored snapshot has non-success fetch status
- WHEN unchanged detection runs
- THEN that snapshot is ignored as previous

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

The system SHALL mark a previously known endpoint removed only after at least two
successful snapshots both omit it and the newest successful omission is at least
five minutes old. Failed snapshots SHALL NOT count toward previous-success or
unchanged-catalog decisions.

#### Scenario: Fewer than two snapshots
- GIVEN fewer than two snapshots exist
- WHEN removal protection evaluates an omitted endpoint
- THEN it does not mark removed

#### Scenario: Not both snapshots successful
- GIVEN the relevant snapshots are not both successful
- WHEN removal protection evaluates an omitted endpoint
- THEN it does not mark removed

#### Scenario: Omission too young
- GIVEN two successful omissions exist but the newest is younger than five minutes
- WHEN removal protection evaluates an omitted endpoint
- THEN it does not mark removed

### Requirement: Live OmniRoute catalog fetch

The system SHALL fetch the provider accounts (`GET /api/providers`) and the model
catalog (`GET /api/v1/providers/{provider}/models` per provider, or
`GET /v1/models`) from OmniRoute before each daily catalog scan, unless a catalog
payload is explicitly injected by tests or offline tooling. The fetch SHALL use the
configured OmniRoute base URL and credentials, apply bounded retries on transient
failures, and raise a structured error on auth failure, non-2xx status, or
invalid payload. A failed fetch SHALL record a failed snapshot and SHALL NOT
fabricate or overwrite the previous catalog.

#### Scenario: Catalog fetched before scan
- GIVEN no catalog payload is injected and OmniRoute credentials are configured
- WHEN the daily catalog scan starts
- THEN the provider/model catalog is fetched from the OmniRoute management API
- AND the parsed catalog is passed to the scan

#### Scenario: Fetch failure does not overwrite
- GIVEN the OmniRoute catalog fetch fails with a non-2xx status
- WHEN the scan runs
- THEN a failed snapshot is recorded
- AND the previous catalog is left unchanged
