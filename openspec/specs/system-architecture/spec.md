# system-architecture Specification

## Purpose
TBD - created by archiving change add-foundation. Update Purpose after archive.
## Requirements
### Requirement: Provider endpoint is the unit of management

The system SHALL treat a `provider_endpoint` (provider account + provider model
id) as the unit of management, not the canonical model, because one canonical
model can have several endpoints with different access status, latency
and availability.

#### Scenario: Same model on two providers
- GIVEN one canonical model offered by provider A and provider B
- WHEN endpoints are built
- THEN two independent provider_endpoints exist, each carrying its own access and
  status

### Requirement: Daily batch is the main process

The system SHALL run the full pipeline once per day; additional runs are manual
or event-driven. The system SHALL NOT require sub-daily health or quota loops -
intraday endpoint failures are handled by OmniRoute fallback and circuit breaker.

#### Scenario: Intraday failure not rebuilt
- GIVEN an endpoint fails mid-day
- WHEN a production request hits it
- THEN OmniRoute fails over and the orchestrator does not rebuild combos until
  the next daily batch

### Requirement: Apply preconditions and transaction boundaries

The system SHALL NOT change OmniRoute when PostgreSQL is unavailable, no current
snapshot exists, the desired state failed validation, an access rule is
stale/conflicting, or the endpoint failed probe.

#### Scenario: Missing snapshot blocks apply
- GIVEN no snapshot of current OmniRoute state exists
- WHEN an apply is attempted
- THEN the apply is refused

### Requirement: Idempotent runs

The system SHALL use idempotency keys (catalog snapshot, probe, combo apply) so
that repeating a run creates no duplicate models or aliases, makes no diff-free
combo change, and does not re-run an expensive probe whose inputs are unchanged.

#### Scenario: Re-run with unchanged inputs
- GIVEN a completed daily run
- WHEN the same run repeats with unchanged inputs
- THEN no combo change is applied and unchanged probes are skipped

### Requirement: Forbidden state transitions

The system SHALL reject the transitions: `excluded_unknown -> active` without
new confirmed access evidence; `probe_failed -> active` without a new successful
probe; `planned -> applied` without a saved snapshot.

#### Scenario: Reactivate failed endpoint too early
- GIVEN an endpoint failed a probe
- WHEN no later successful probe exists
- THEN the endpoint cannot transition to `active`

### Requirement: Composition root stays within a single-responsibility boundary

The production composition root SHALL wire stages, the CLI dispatcher, and the
AA-index handlers from focused per-domain modules rather than defining them all
in one module. No single composition module SHALL own stage adapters across
unrelated domains together with the CLI dispatcher and the AA-index handlers.
Refactoring the composition layout SHALL NOT change any stage behavior, exit
code, persisted shape, or CLI surface; the existing test suite SHALL pass
unchanged as the behavior-preservation oracle.

#### Scenario: Stage domains live in separate modules
- **WHEN** the composition layer is inspected
- **THEN** stage adapters are grouped by domain in dedicated modules, the CLI
  dispatcher and AA-index handlers are separate, and the composition root only
  wires them together

#### Scenario: Refactor preserves behavior
- **WHEN** the composition root is decomposed into per-domain modules
- **THEN** the full existing pytest suite passes unchanged
- **AND** no stage behavior, exit code, persisted shape, or CLI command changes

### Requirement: OmniRoute write surface is combos plus additive free-model registration

The orchestrator's writes to OmniRoute SHALL be limited to two operations:
mutating `fmo-` combos, and additively registering confirmed-free
provider-models under existing connections. It SHALL NOT create providers or
connections because credentials are owned by the operator, SHALL NOT delete
provider-models, and SHALL NOT write any paid model. All other OmniRoute
interaction remains read-only.

#### Scenario: Registration is the only added write
- GIVEN the orchestrator runs against OmniRoute
- WHEN it mutates OmniRoute
- THEN it either changes an `fmo-` combo or additively registers a confirmed-free
  provider-model under an existing connection
- AND it never creates a provider/connection, deletes a provider-model, or writes
  a paid model

### Requirement: Persistence layer is a package of per-aggregate modules

The persistence layer SHALL be a `fmo.persistence` package with one module per
domain aggregate over a shared `_base` module that owns the `Database`,
`Repository`, and module-private row helpers (`_one`, `_optional`, `_many`,
`_jsonb`, content/hash helpers). No single aggregate module SHALL own the
repositories of unrelated aggregates, and table SQL SHALL remain confined to its
aggregate's repository module. Splitting the layer SHALL NOT change any persisted
shape, query, or repository behavior; the existing test suite SHALL pass
unchanged as the behavior-preservation oracle.

#### Scenario: Persistence layer is split into per-aggregate modules
- **WHEN** the persistence layer is inspected
- **THEN** `fmo.persistence` is a package with one module per aggregate and a
  shared `_base` module owning `Database`, `Repository`, and the row helpers
- **AND** no aggregate module defines repositories for an unrelated aggregate

#### Scenario: Persistence public API stays import-stable
- **WHEN** existing call sites import `Database`, `Repository`, or any
  `*Repository` from `fmo.persistence`
- **THEN** every previously public name resolves unchanged through the package
  `__init__` re-export
- **AND** the full existing pytest suite passes unchanged

### Requirement: Discovery, quota, and access stages are dedicated modules

The front-of-pipeline stages SHALL be **defined** in dedicated per-cluster
modules under the `fmo.composition_stages` package — metadata, free-candidate and
account discovery, model matching, and access classification — each owning its
own private helpers, rather than in a single stage module. The
module that fronts a front-of-pipeline stage SHALL contain the stage's
implementation rather than a delegation to another module (in particular not to
`_legacy`). Draining these clusters SHALL NOT change any stage behavior, persisted
shape, or the production stage-adapter wiring; the existing test suite SHALL pass
unchanged as the behavior-preservation oracle.

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

#### Scenario: Stage package re-exports preserve composition wiring
- **WHEN** `composition.py` and `_production_stage_adapters()` resolve the moved
  stages
- **THEN** every stage and shared name resolves unchanged through the package
  re-export
- **AND** the full existing pytest suite passes unchanged

### Requirement: Probing, telemetry, inventory, and role stages are dedicated modules

The middle-of-pipeline stages SHALL be **defined** in dedicated per-cluster
modules under the `fmo.composition_stages` package — probing, telemetry sync,
Hermes inventory, role lifecycle, and role scoring. The role-scoring helper
cluster (health/stability/latency components, quality-band seeding, AA-metric and
health lookups) SHALL be defined with the role stage rather than in the package
root. The module that fronts a middle-of-pipeline stage SHALL contain the stage's
implementation rather than a delegation to another module (in particular not to
`_legacy`). Draining these clusters SHALL NOT change any stage behavior, scoring
output, or persisted shape; the existing test suite SHALL pass unchanged as the
behavior-preservation oracle.

#### Scenario: Probing, telemetry, inventory, and role stages live in dedicated modules
- **WHEN** the composition stages package is inspected
- **THEN** the probing, telemetry-sync, Hermes-inventory, role-lifecycle, and
  role-scoring stages live in separate cluster modules under
  `fmo.composition_stages`
- **AND** all stages still resolve unchanged through the production adapter table

#### Scenario: Middle-of-pipeline stages are defined in their own modules
- **WHEN** a middle-of-pipeline stage entrypoint is inspected with
  `inspect.getmodule`
- **THEN** it resolves to its cluster module (`probing`, `telemetry`, `inventory`,
  or `roles`)
- **AND** it does not resolve to `fmo.composition_stages._legacy`

#### Scenario: Role scoring helpers move with the role stage
- **WHEN** the role module is inspected
- **THEN** the health/stability/latency components, quality-band seeding, and
  AA/health lookup helpers are defined alongside the role stage
- **AND** the full existing pytest suite passes unchanged

### Requirement: Allocation, apply, rollback, and audit stages are dedicated modules

The back-of-pipeline stages SHALL be **defined** in dedicated per-cluster modules
under the `fmo.composition_stages` package — demand forecast, allocation, diff,
apply, rollback, and audit — and the cross-cluster shared helpers (effect/result,
slug/hash, adapter helpers) SHALL be defined once in a single helpers
module imported by the domain modules. The module that fronts a back-of-pipeline
stage SHALL contain the stage's implementation rather than a delegation to another
module. After the drain the package SHALL contain only the re-export shim, the
cluster stage modules, the `_helpers` module, and the `_base` module holding the
stage dataclasses and base adapter builder; no `_legacy` delegation module SHALL
remain. The split SHALL NOT change any stage behavior, apply-safety decision,
persisted shape, or exit code; the existing test suite SHALL pass unchanged as the
behavior-preservation oracle.

#### Scenario: Allocation, apply, rollback, and audit stages live in dedicated modules
- **WHEN** the composition stages package is inspected
- **THEN** the allocation, apply, rollback, and audit stages are defined in
  separate cluster modules under `fmo.composition_stages`
- **AND** no `_legacy` or other monolithic stage module remains alongside the
  package

#### Scenario: Shared stage helpers live in one helpers module
- **WHEN** a domain stage module uses a cross-cluster helper
- **THEN** that helper is imported from the single shared helpers module rather
  than redefined per cluster
- **AND** the full existing pytest suite passes unchanged

### Requirement: Shared test fakes and per-domain composition tests

Shared test fakes SHALL live in a dedicated `tests` support module rather than
inline in a single test file (fake OmniRoute/ops clients, LLM runtimes, and
instructor clients), and the composition tests SHALL be split into per-domain
files that
mirror the stage cluster modules, with every `@pytest.mark.spec` binding moving
with its test. The test suite SHALL collect and run identically under both
`pytest` and `python -m pytest`. Reorganizing the tests SHALL NOT drop any
scenario binding; `test_spec_coverage.py` is the oracle that coverage is
preserved.

#### Scenario: Test fakes live in a shared test-support module
- **WHEN** a test needs a fake ops client, LLM runtime, or instructor client
- **THEN** it imports the fake from the shared `tests` support module
- **AND** no composition test file redefines those fakes inline

#### Scenario: Composition tests mirror the stage packages
- **WHEN** the composition tests are inspected
- **THEN** they are split into per-domain files mirroring the stage cluster
  modules, with each `@pytest.mark.spec` marker carried alongside its test
- **AND** `test_spec_coverage.py` reports every previously bound scenario still
  bound

#### Scenario: Test suite runs from both pytest entry points
- **WHEN** the suite is collected via either `pytest` or `python -m pytest`
- **THEN** the `tests` package resolves without depending on the current working
  directory being on `sys.path`
- **AND** both entry points collect and pass the same tests

### Requirement: Shared helpers have a single canonical definition

Duplicated cross-module helpers SHALL each have exactly one canonical definition,
with call sites importing it rather than reimplementing: the repository row
helpers live in `persistence/_base`; the timestamp (`utcnow`), slug, hashing, and
access-state helpers live in one shared module each. Stage cluster modules SHALL
import the canonical helper name directly from its module; the
`composition_stages._helpers` module SHALL NOT carry a per-package re-export
alias layer (e.g. `_canonical_slug = canonical_slug`) for those helpers.
Consolidation SHALL NOT change any
behavior — it removes duplicate definitions and redundant aliases only; the
existing test suite SHALL pass unchanged as the behavior-preservation oracle.

#### Scenario: Row access helpers are defined once in the persistence base
- **WHEN** a module needs a repository row helper (`_one`, `_optional`, `_many`,
  `_jsonb`, `_content_hash`)
- **THEN** it imports the single definition from `persistence/_base`
- **AND** no stage module reimplements the helper

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

### Requirement: Stage bodies are defined in their domain modules

Each pipeline stage and its private helpers SHALL be **defined** in the domain
module under `fmo.composition_stages` that owns its cluster — not re-exported
there from a shared catch-all module. No `_legacy` (or otherwise named single
delegation/monolith) module SHALL remain under `fmo.composition_stages`; besides
the `__init__` re-export shim, the package SHALL contain only the cluster stage
modules, the cross-cluster `_helpers` module, and the shared `_base` module (the
`Stage*` dataclasses and the base `_production_stage_adapters` builder). Draining
the bodies SHALL NOT change any stage behavior, apply-safety decision, persisted
shape, idempotency key, or exit code; the existing test suite SHALL pass unchanged
as the behavior-preservation oracle, and the package's public re-export surface
SHALL stay identical.

#### Scenario: Each stage resolves to its own domain module
- **WHEN** a stage entrypoint exposed by the `fmo.composition_stages` package is
  inspected with `inspect.getmodule`
- **THEN** it resolves to the cluster module that owns it (e.g. `_apply_stage` to
  `fmo.composition_stages.apply`)
- **AND** it does not resolve to a `fmo.composition_stages._legacy` module

#### Scenario: No legacy delegation module remains
- **WHEN** the `fmo.composition_stages` package directory is inspected
- **THEN** there is no `_legacy` module and no package module imports `_legacy`
- **AND** the full existing pytest suite passes unchanged
