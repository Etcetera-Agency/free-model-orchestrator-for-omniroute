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

