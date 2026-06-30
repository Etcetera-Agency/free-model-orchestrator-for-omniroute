# system-architecture Specification

## MODIFIED Requirements

### Requirement: Provider endpoint is the unit of management

The system SHALL treat a `provider_endpoint` (provider account + provider model
id) as the unit of management, not the canonical model, because one canonical
model can have several endpoints with different access status, latency and
availability.

#### Scenario: Same model across providers
- GIVEN one canonical model offered by provider A and provider B
- WHEN endpoints are built
- THEN two independent provider_endpoints exist, each carrying its own access
  and status

### Requirement: Daily batch is the main process

The system SHALL run the full pipeline once per day; additional runs are manual
or event-driven. The system SHALL NOT require sub-daily health or quota loops —
intraday endpoint failures are handled by OmniRoute fallback and circuit breaker.

#### Scenario: No hourly orchestrator
- WHEN no manual trigger exists
- THEN the orchestrator runs only at the daily cadence

### Requirement: Apply preconditions and transaction boundaries

The system SHALL NOT change OmniRoute when PostgreSQL is unavailable, no current
snapshot exists, the desired state failed validation, access evidence is stale or
conflicting, or the endpoint failed probe.

#### Scenario: Missing snapshot blocks apply
- GIVEN no current combo snapshot exists
- WHEN apply is requested
- THEN no OmniRoute mutation is made

### Requirement: Idempotent runs

The system SHALL use idempotency keys (catalog snapshot, probe, combo apply) so
that repeating a run creates no duplicate models or aliases, makes no diff-free
combo change, and does not re-run an expensive probe when the input hash is
unchanged.

#### Scenario: Re-run unchanged input
- GIVEN a run already processed the same catalog/probe/apply input
- WHEN the run repeats
- THEN no duplicate state is written

### Requirement: Forbidden state transitions

The system SHALL reject the transitions: `excluded_unknown → active` without new
confirmed access evidence; `probe_failed → active` without a new successful
probe; `planned → applied` without a saved snapshot.

#### Scenario: Reactivate failed endpoint too early
- GIVEN an endpoint failed a probe
- WHEN no later successful probe exists
- THEN the endpoint cannot transition to `active`

### Requirement: Discovery, quota, and access stages are dedicated modules

The front-of-pipeline stages SHALL be **defined** in dedicated per-cluster
modules under the `fmo.composition_stages` package — metadata, free-candidate and
account discovery, model matching, and access classification — each owning its
own private helpers, rather than in a single stage module. The module that fronts
a front-of-pipeline stage SHALL contain the stage's implementation rather than a
delegation to another module. FMO SHALL NOT include a quota stage module.

#### Scenario: Discovery and access stages live in dedicated modules
- **WHEN** the composition stages package is inspected
- **THEN** the discovery and access-classification stages live in separate
  cluster modules under `fmo.composition_stages`
- **AND** no extracted module defines a stage belonging to a different cluster

#### Scenario: Front-of-pipeline stages are defined in their own modules
- **WHEN** a front-of-pipeline stage entrypoint is inspected with
  `inspect.getmodule`
- **THEN** it resolves to its cluster module (`discovery` or `access`)
- **AND** it does not resolve to `fmo.composition_stages._legacy`

### Requirement: Shared helpers have a single canonical definition

Cross-cluster helper behavior SHALL have a single canonical implementation, with
call sites importing it rather than reimplementing: the repository row helpers
live in `persistence/_base`; the timestamp (`utcnow`), slug, hashing and
access-state helpers live in one shared module each. Stage cluster modules SHALL
import the canonical helper name directly from its module; the
`composition_stages._helpers` module SHALL NOT carry a per-package re-export
alias layer.

#### Scenario: Timestamp and hashing helpers are centralized
- **WHEN** a module needs the UTC-now, canonical-slug, hash, idempotency-key, or
  access-state helper
- **THEN** it imports the one canonical definition for that helper
- **AND** the full existing pytest suite passes unchanged

#### Scenario: Stage helpers carry no re-export alias layer
- **WHEN** the `composition_stages._helpers` module is inspected
- **THEN** it defines only the genuine cross-cluster stage helpers and no
  underscore re-export alias for the centralized helpers
- **AND** the cluster modules import those helpers directly from their canonical
  modules
