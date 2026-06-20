## ADDED Requirements

### Requirement: Persistent run-lock storage

The system SHALL persist the global daily-run lock, per-provider scan locks and
the global combo-apply lock in PostgreSQL via the repository layer, and SHALL
release them when a run finishes or fails, so locks survive within a run and
across process boundaries.

#### Scenario: Daily lock blocks a concurrent run
- **WHEN** a daily run holds the global daily-run lock
- **THEN** a second daily run does not start until the lock is released

#### Scenario: Lock released on failure
- **WHEN** a run fails while holding a lock
- **THEN** the lock is released so a later run can acquire it

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
