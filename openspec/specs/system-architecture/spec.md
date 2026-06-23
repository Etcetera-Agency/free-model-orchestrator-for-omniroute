# system-architecture Specification

## Purpose
TBD - created by archiving change add-foundation. Update Purpose after archive.
## Requirements
### Requirement: Provider endpoint is the unit of management

The system SHALL treat a `provider_endpoint` (provider account + provider model
id) as the unit of management, not the canonical model, because one canonical
model can have several endpoints with different quotas, reset policies, latency
and availability.

#### Scenario: Same model on two providers
- GIVEN one canonical model offered by provider A and provider B
- WHEN endpoints are built
- THEN two independent provider_endpoints exist, each carrying its own quota and
  status

### Requirement: Daily batch is the main process

The system SHALL run the full pipeline once per day; additional runs are manual
or event-driven. The system SHALL NOT require sub-daily health or quota loops —
intraday endpoint failures are handled by OmniRoute fallback and circuit breaker.

#### Scenario: Intraday failure not rebuilt
- GIVEN an endpoint fails mid-day
- WHEN a production request hits it
- THEN OmniRoute fails over and the orchestrator does not rebuild combos until
  the next daily batch

### Requirement: Apply preconditions and transaction boundaries

The system SHALL NOT change OmniRoute when PostgreSQL is unavailable, no current
snapshot exists, the desired state failed validation, an access rule is
stale/conflicting, quota is unknown, or the endpoint failed probe.

#### Scenario: Missing snapshot blocks apply
- GIVEN no snapshot of current OmniRoute state exists
- WHEN an apply is attempted
- THEN the apply is refused

### Requirement: Idempotent runs

The system SHALL use idempotency keys (catalog snapshot, quota source, quota
rule, probe, combo apply) so that repeating a run creates no duplicate models or
aliases, makes no diff-free combo change, and does not re-run an expensive probe
whose inputs are unchanged.

#### Scenario: Re-run with unchanged inputs
- GIVEN a completed daily run
- WHEN the same run repeats with unchanged inputs
- THEN no combo change is applied and unchanged probes are skipped

### Requirement: Forbidden state transitions

The system SHALL reject the transitions: `excluded_unknown → active` without a
new confirmed quota rule; `quota_exhausted → active` before reset and quota
refresh; `probe_failed → active` without a new successful probe; `planned →
applied` without a saved snapshot.

#### Scenario: Reactivate exhausted endpoint too early
- GIVEN an endpoint in `quota_exhausted`
- WHEN reset has not occurred and quota is not refreshed
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

The front-of-pipeline stages SHALL live in dedicated per-cluster modules under
the `fmo.composition_stages` package — metadata, free-candidate and account
discovery, model matching, quota research/sync, and access classification — each
owning its own private helpers, rather than in a single stage module. Extracting
these clusters SHALL NOT change any stage behavior, persisted shape, or the
production stage-adapter wiring; the existing test suite SHALL pass unchanged as
the behavior-preservation oracle.

#### Scenario: Discovery, quota, and access stages live in dedicated modules
- **WHEN** the composition stages package is inspected
- **THEN** the discovery, quota-research/sync, and access-classification stages
  live in separate cluster modules under `fmo.composition_stages`
- **AND** no extracted module defines a stage belonging to a different cluster

#### Scenario: Stage package re-exports preserve composition wiring
- **WHEN** `composition.py` and `_production_stage_adapters()` resolve the moved
  stages
- **THEN** every stage and shared name resolves unchanged through the package
  re-export
- **AND** the full existing pytest suite passes unchanged

### Requirement: Probing, telemetry, inventory, and role stages are dedicated modules

The middle-of-pipeline stages SHALL live in dedicated per-cluster modules under
the `fmo.composition_stages` package — probing, telemetry sync, Hermes inventory,
role lifecycle, and role scoring. The role-scoring helper cluster
(health/stability/latency components, quality-band seeding, AA-metric and health
lookups) SHALL live with the role stage rather than in the package root.
Extracting these clusters SHALL NOT change any stage behavior, scoring output, or
persisted shape; the existing test suite SHALL pass unchanged as the
behavior-preservation oracle.

#### Scenario: Probing, telemetry, inventory, and role stages live in dedicated modules
- **WHEN** the composition stages package is inspected
- **THEN** the probing, telemetry-sync, Hermes-inventory, role-lifecycle, and
  role-scoring stages live in separate cluster modules under
  `fmo.composition_stages`
- **AND** all stages still resolve unchanged through the production adapter table

#### Scenario: Role scoring helpers move with the role stage
- **WHEN** the role module is inspected
- **THEN** the health/stability/latency components, quality-band seeding, and
  AA/health lookup helpers are defined alongside the role stage
- **AND** the full existing pytest suite passes unchanged

### Requirement: Allocation, apply, rollback, and audit stages are dedicated modules

The back-of-pipeline stages SHALL live in dedicated per-cluster modules under the
`fmo.composition_stages` package — demand forecast, allocation, diff, apply,
rollback, and audit — and the cross-cluster shared helpers (effect/result,
slug/hash, quota-math, adapter helpers) SHALL be defined once in a single helpers
module imported by the domain modules. After the split the
package root SHALL contain only the re-export shim and the stage dataclasses; no
monolithic stage module SHALL remain. The split SHALL NOT change any stage
behavior, apply-safety decision, persisted shape, or exit code; the existing test
suite SHALL pass unchanged as the behavior-preservation oracle.

#### Scenario: Allocation, apply, rollback, and audit stages live in dedicated modules
- **WHEN** the composition stages package is inspected
- **THEN** the allocation, apply, rollback, and audit stages live in separate
  cluster modules under `fmo.composition_stages`
- **AND** no monolithic `composition_stages` module remains alongside the package

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
