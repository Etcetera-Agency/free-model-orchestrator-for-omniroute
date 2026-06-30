# scheduler Specification

## Purpose
Define locked scheduler triggers for publisher pipeline runs.

## Requirements

### Requirement: Scheduler triggers publisher pipeline under a lock
The scheduler SHALL run daily/manual/urgent publisher pipelines only when it
owns the run lock.

#### Scenario: Scheduler fires at cron time
- **WHEN** the configured cron time arrives
- **THEN** the scheduler starts a run.

#### Scenario: Scheduled daily run
- **WHEN** a daily schedule fires
- **THEN** the daily run is triggered.

#### Scenario: Service fires the daily run
- **WHEN** the service tick reaches schedule
- **THEN** the scheduler runner is called.

#### Scenario: Manual trigger starts a run
- **WHEN** a manual trigger is requested
- **THEN** a run starts immediately.

#### Scenario: Urgent trigger runs out of schedule
- **WHEN** an urgent trigger is requested
- **THEN** a run starts outside cron time.

#### Scenario: Urgent run after paid charge
- **WHEN** an urgent paid-charge signal is observed
- **THEN** a publisher run is requested.

#### Scenario: Overlapping daily runs
- **WHEN** a daily run is already active
- **THEN** another daily run does not start.

#### Scenario: Daily lock blocks a concurrent run
- **WHEN** the daily lock is held
- **THEN** concurrent starts are blocked.

#### Scenario: Concurrent start blocked by the lock
- **WHEN** two starts compete
- **THEN** one fails to acquire the lock.

#### Scenario: Concurrent repository acquisition has one winner
- **WHEN** two repositories acquire the same lock
- **THEN** only one token is returned.

#### Scenario: Lock released on failure
- **WHEN** a run fails
- **THEN** the lock is released.

#### Scenario: Metadata sync failure is conservative
- **WHEN** a publisher prerequisite fails on an external dependency
- **THEN** the run fails conservatively instead of reporting success.

#### Scenario: Apply pipeline runs
- **WHEN** a scheduled run is due
- **THEN** the current publisher pipeline runs.
