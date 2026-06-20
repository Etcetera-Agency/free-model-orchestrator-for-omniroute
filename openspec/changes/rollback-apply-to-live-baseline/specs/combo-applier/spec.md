## MODIFIED Requirements

### Requirement: Rollback on failure

The system SHALL restore the pre-change baseline, re-read, smoke-test the restored
version and mark the run failed when apply or smoke test fails. The pre-change
baseline SHALL be the live combo state captured immediately before the mutation
(the same read used for the hash/precondition check), NOT the `before` value
recorded at diff time. If the live state captured at apply time differs from the
diff-time `before`, the applier SHALL follow the drift-protection path (create a
conflict / require force) instead of overwriting.

#### Scenario: Smoke test fails
- GIVEN the post-apply smoke test fails
- WHEN failure is handled
- THEN the combo is restored to the live state captured immediately before the
  mutation and the run is marked failed

#### Scenario: Live state diverged from diff-time before
- GIVEN the live combo state at apply time differs from the `before` recorded at
  diff time
- WHEN apply starts
- THEN the applier follows the drift-protection path rather than overwriting with
  the stale diff-time value
