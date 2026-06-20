# scheduler Specification

## Purpose
TBD - created by archiving change add-foundation. Update Purpose after archive.
## Requirements
### Requirement: Daily batch pipeline

The system SHALL execute the full daily pipeline once per day at the configured
cron time, ordered so discovery precedes quota research, scoring, allocation,
combo build, minimal diff, apply, smoke test and audit. Routine sub-daily (5-min
/ hourly) cron jobs SHALL NOT be required.

#### Scenario: Scheduled daily run
- GIVEN the configured daily cron time arrives
- WHEN the scheduler fires
- THEN the full pipeline runs end to end in order

### Requirement: Run locks

The system SHALL hold a global daily-run lock, per-provider scan locks and a
global combo-apply lock. A new daily run SHALL NOT start while a previous one is
unfinished.

#### Scenario: Overlapping daily runs
- GIVEN a daily run is in progress
- WHEN another daily run is triggered
- THEN the second run does not start until the first finishes

### Requirement: Additional run triggers

The system SHALL allow manual full runs, manual provider runs, manual role
rebuilds, event-driven runs after a provider is added, and urgent runs after a
paid charge is detected.

#### Scenario: Urgent run after paid charge
- GIVEN a paid charge is explicitly detected
- WHEN an urgent run is requested
- THEN an out-of-schedule run is allowed

### Requirement: No combo test endpoint

The scheduler SHALL never call `/api/combos/test`.

#### Scenario: Apply pipeline runs
- GIVEN combos are being applied
- WHEN the pipeline executes
- THEN `/api/combos/test` is not called

### Requirement: Daily orchestration order

The daily scheduler SHALL sync external metadata before dependent pipeline
stages. It SHALL fetch models.dev before free candidate discovery and SHALL fetch
Artificial Analysis with a configured API key before role scoring and AA
index migration checks.

#### Scenario: External metadata before discovery and scoring
- GIVEN the daily scheduler starts a full run
- WHEN the run reaches metadata sync
- THEN models.dev catalog sync completes before candidate discovery
- AND authenticated Artificial Analysis sync completes before scoring and AA index migration detection

#### Scenario: Metadata sync failure is conservative
- GIVEN models.dev or Artificial Analysis metadata sync fails
- WHEN the daily scheduler evaluates dependent stages
- THEN dependent stages do not consume partial failed payloads
- AND the run records an external dependency failure

### Requirement: Persistent run-lock storage

The system SHALL persist the global daily-run lock, per-provider scan locks and
the global combo-apply lock in PostgreSQL via the repository layer, and SHALL
release them when a run finishes or fails, so locks survive within a run and
across process boundaries. Active held locks SHALL be protected by a
database-enforced uniqueness rule so acquiring a lock is atomic across
independent processes and connections.

#### Scenario: Daily lock blocks a concurrent run
- **WHEN** a daily run holds the global daily-run lock
- **THEN** a second daily run does not start until the lock is released

#### Scenario: Lock released on failure
- **WHEN** a run fails while holding a lock
- **THEN** the lock is released so a later run can acquire it

#### Scenario: Concurrent repository acquisition has one winner
- **GIVEN** two independent PostgreSQL connections attempt to acquire the same
  logical run-lock at the same time
- **WHEN** both acquisitions complete
- **THEN** exactly one acquisition returns a lock token
- **AND** exactly one active held lock row exists for that logical lock name

### Requirement: Cron-driven daily firing

The system SHALL fire the full pipeline at the time given by
`HERMES_INVENTORY_CRON`, and SHALL support manual full, manual provider, manual
role, event-driven, and urgent triggers as additional run starts. The scheduler
SHALL never call `/api/combos/test`.

#### Scenario: Scheduler fires at cron time
- **WHEN** the configured cron time arrives
- **THEN** the scheduler starts a full pipeline run

#### Scenario: Manual trigger starts a run
- **WHEN** a manual or event-driven trigger is requested
- **THEN** an out-of-schedule run starts subject to the run locks

### Requirement: Scheduler service entrypoint

The system SHALL provide a runnable scheduler entrypoint that hosts the cron loop
driven by `HERMES_INVENTORY_CRON`, dispatches full pipeline runs through the
production runner, and routes cron, manual, event-driven, and urgent triggers
through the persistent run-lock so that no two runs execute concurrently. The
entrypoint SHALL never call `/api/combos/test`.

#### Scenario: Service fires the daily run
- **WHEN** the scheduler entrypoint is running and the configured cron time
  arrives
- **THEN** it acquires the daily run-lock and starts a full pipeline run through
  the production runner

#### Scenario: Concurrent start blocked by the lock
- **WHEN** a second run is triggered while the daily run-lock is held
- **THEN** the second run does not begin until the lock is released

#### Scenario: Urgent trigger runs out of schedule
- **WHEN** an urgent trigger is requested after a paid-charge signal
- **THEN** an out-of-schedule run starts subject to the run-lock
