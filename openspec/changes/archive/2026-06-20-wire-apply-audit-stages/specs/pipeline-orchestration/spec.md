## ADDED Requirements

### Requirement: Apply and audit stages produce real effects

The composed runtime SHALL drive the `apply` and `audit` stages through their
existing domain modules. The production `apply` stage SHALL evaluate
repository-backed preconditions, apply the minimal diff transactionally to only
`fmo-` combos, run a real combo smoke test, and roll back on failure. The CLI
`combo_test_called` signal SHALL reflect whether the real smoke test ran and
SHALL NOT be hardcoded. The `audit` stage SHALL persist audit records and
snapshots. Outcomes SHALL map to exit codes `unsafe_to_apply` (5),
`apply_failed_rolled_back` (6), and `rollback_failed` (7).

#### Scenario: Production apply runs the real smoke test
- **WHEN** the `apply` stage applies a combo diff
- **THEN** the applier and a real transactional smoke test are invoked
- **AND** the CLI reports `combo_test_called` as true from the real signal
- **AND** an adapter returning success without applying or smoke-testing fails the suite

#### Scenario: Failing guard blocks apply
- **WHEN** a repository-backed apply precondition fails
- **THEN** the run returns `unsafe_to_apply` and OmniRoute is not mutated

#### Scenario: Smoke failure rolls back
- **WHEN** the apply smoke test fails
- **THEN** the change is rolled back and the run returns `apply_failed_rolled_back`
- **AND** a failed rollback returns `rollback_failed`

#### Scenario: Audit persists records
- **WHEN** the `audit` stage runs after apply
- **THEN** audit records and snapshots are persisted through the repository
- **AND** an adapter returning success without writing audit records fails the suite
