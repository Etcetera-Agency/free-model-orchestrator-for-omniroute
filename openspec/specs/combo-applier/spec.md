# combo-applier Specification

## Purpose
TBD - created by archiving change add-allocation. Update Purpose after archive.
## Requirements
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

### Requirement: Apply preconditions evaluated at the entrypoint

The entrypoint SHALL compute apply preconditions by evaluating the apply guard —
database availability, a saved snapshot, a valid desired state, quota safety, and
a passing probe/smoke result — and SHALL pass that computed value into CLI
dispatch instead of a hardcoded value. The evaluation SHALL fail closed: any
unknown, stale, or unavailable input yields preconditions `False`.

#### Scenario: Failing guard input blocks apply
- **WHEN** any apply-guard input is failing, unknown, or stale at the entrypoint
- **THEN** apply preconditions are `False`
- **AND** `apply` exits with code 5 (unsafe) and changes nothing

#### Scenario: Healthy guard inputs allow apply
- **WHEN** every apply-guard input is healthy at the entrypoint
- **THEN** apply preconditions are `True`
- **AND** `apply` is allowed to proceed through the runner's gating

### Requirement: Production apply invokes the real smoke path

The composed production runtime SHALL invoke the combo applier and its
transactional smoke test when the `apply` stage runs; it SHALL NOT report a
fabricated combo-test signal. The smoke test SHALL exercise the applied `fmo-`
combos through the existing OmniRoute path and SHALL NEVER call
`/api/combos/test`. When the smoke test fails, the runtime SHALL roll back the
applied diff.

#### Scenario: Production apply smoke-tests applied combos
- **WHEN** the production `apply` stage applies a combo diff
- **THEN** the transactional smoke test runs against the applied `fmo-` combos
- **AND** the runtime never calls `/api/combos/test`

#### Scenario: Fabricated smoke signal rejected
- **WHEN** the apply adapter reports the combo-test signal
- **THEN** the signal reflects whether the real smoke test ran
- **AND** a hardcoded or fabricated combo-test signal fails the executable suite

