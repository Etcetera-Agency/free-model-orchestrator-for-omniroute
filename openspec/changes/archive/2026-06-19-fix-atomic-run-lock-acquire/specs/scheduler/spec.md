## MODIFIED Requirements

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
