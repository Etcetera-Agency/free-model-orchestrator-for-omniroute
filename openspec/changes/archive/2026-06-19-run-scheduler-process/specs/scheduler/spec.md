## ADDED Requirements

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
