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
