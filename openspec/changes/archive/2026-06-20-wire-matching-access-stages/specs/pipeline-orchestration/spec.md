## ADDED Requirements

### Requirement: Matching and access stages produce real effects

The composed runtime SHALL drive the `model-matching`, `quota-research`, and
`access-classification` stages through their existing domain modules and persist
their real output through the repository. Each stage SHALL report `success` only
when its declared effect is observable, and SHALL fail closed otherwise. Access
status SHALL use the canonical vocabulary `confirmed | inferred | assumed_shared
| unknown`, and `unknown` SHALL NOT be treated as free access.

#### Scenario: Matching writes endpoint bindings
- **WHEN** the `model-matching` stage runs over discovered free candidates
- **THEN** matched provider-endpoint rows are written through the repository
- **AND** an adapter returning success without writing matches fails the suite

#### Scenario: Quota research persists capped rules
- **WHEN** the `quota-research` stage extracts quota bounds
- **THEN** content-hashed quota snapshots and rules are persisted
- **AND** summary-sourced rules are capped by `summary_confidence_cap`

#### Scenario: Access classification persists status
- **WHEN** the `access-classification` stage classifies an endpoint
- **THEN** its status and evidence are persisted with one of the canonical values
- **AND** an `unknown` status is never recorded as free access

#### Scenario: External payload missing fails closed
- **WHEN** a required external payload for any of these stages is missing or stale
- **THEN** the stage returns `external_dependency_failed` or `partial_stale`
- **AND** dependent stages do not run
