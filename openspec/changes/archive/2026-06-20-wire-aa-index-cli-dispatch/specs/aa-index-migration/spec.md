## ADDED Requirements

### Requirement: Migration agent runs in production via the shared runtime

The production migration capability SHALL invoke `run_migration_agent` over the
shared Instructor runtime for the `analyze`/`proposal` steps. The LLM output is
an advisory threshold proposal only; deterministic code SHALL own freeze on AA
version change, proposal validation, approval, rollout, and smoke-fail rollback.
When AA fetch fails or no migration model is available, the capability SHALL fail
closed and keep existing combos and thresholds frozen.

#### Scenario: Advisory proposal generated
- **WHEN** `aa-index analyze` runs with the runtime available
- **THEN** `run_migration_agent` produces an advisory threshold proposal
- **AND** the proposal is persisted but not auto-applied

#### Scenario: Deterministic approval and rollout
- **WHEN** an operator approves and rolls out a proposal
- **THEN** thresholds change only through the deterministic rollout path
- **AND** a smoke-test failure after rollout triggers deterministic rollback

#### Scenario: AA unavailable freezes thresholds
- **WHEN** the AA fetch fails or no migration model is available
- **THEN** thresholds and combos stay frozen and the run fails closed
