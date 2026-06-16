# scheduler Specification

## ADDED Requirements

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
