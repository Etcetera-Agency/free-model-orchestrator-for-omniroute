# combo-applier Specification

## ADDED Requirements

### Requirement: Manage only fmo- combos

The system SHALL manage only OmniRoute combos whose name carries the configured
managed prefix (`fmo-`) and SHALL NOT modify combos outside that prefix.

#### Scenario: Foreign combo
- GIVEN an OmniRoute combo without the `fmo-` prefix
- WHEN the applier runs
- THEN that combo is left untouched

### Requirement: Transactional apply with smoke test

The system SHALL apply changes under the `combo_apply` advisory lock by:
re-reading current state, verifying its hash is unchanged, saving a snapshot,
applying create/update, reading the combo back, comparing to desired, running a
smoke test via the combo model name, and only then committing the change record.

#### Scenario: State changed under us
- GIVEN the current combo hash changed since planning
- WHEN apply starts
- THEN the apply aborts rather than overwrite the newer state

### Requirement: Rollback on failure

The system SHALL restore the pre-change snapshot, re-read, smoke-test the restored
version and mark the run failed when apply or smoke test fails.

#### Scenario: Smoke test fails
- GIVEN the post-apply smoke test fails
- WHEN failure is handled
- THEN the previous combo is restored and the run is marked failed

### Requirement: Drift protection and anti-churn

The system SHALL detect manual edits to an `fmo-` combo, refuse to overwrite them
automatically, create a conflict requiring force/override, and respect anti-churn
limits (minimum improvement, max changes per run, no apply during incomplete
telemetry sync).

#### Scenario: Manual edit detected
- GIVEN a human changed an `fmo-` combo outside the service
- WHEN the applier detects the drift
- THEN it creates a conflict and does not overwrite without force
