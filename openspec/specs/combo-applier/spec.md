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

### Requirement: Apply stage derives quota and probe safety from persisted state

The production `apply` stage SHALL compute the `quota_safe` and `probes_passed`
apply-precondition inputs from persisted repository state for the endpoints in
the combos it is about to apply, and SHALL NOT use hardcoded values. `quota_safe`
SHALL be true only when every endpoint in the desired combos has a current
quota-safety record with confirmed hard-stop behavior and remaining capacity
above the safety buffer. `probes_passed` SHALL be true only when every endpoint
in the desired combos has a passing, non-stale probe/smoke result. The evaluation
SHALL fail closed: any missing, unknown, or stale input yields the corresponding
value `False`, the stage returns `unsafe_to_apply` (exit 5), and no combo is
mutated.

#### Scenario: Failing quota evidence blocks the apply stage
- **WHEN** an endpoint in a desired `fmo-` combo has a failing, missing, or stale
  quota-safety record at apply time
- **THEN** the stage derives `quota_safe` as `False`
- **AND** the stage returns `unsafe_to_apply` (exit 5) and mutates no combo

#### Scenario: Failing probe evidence blocks the apply stage
- **WHEN** an endpoint in a desired `fmo-` combo lacks a passing, non-stale
  probe/smoke result at apply time
- **THEN** the stage derives `probes_passed` as `False`
- **AND** the stage returns `unsafe_to_apply` (exit 5) and mutates no combo

#### Scenario: Confirmed safety allows the apply stage
- **WHEN** every endpoint in the desired combos is quota-safe above the buffer
  with confirmed hard-stop behavior and has a passing, non-stale probe result
- **THEN** both derived inputs are `True`
- **AND** the apply stage proceeds to mutate the combos

### Requirement: Multi-combo apply is all-or-nothing

When an apply run mutates more than one `fmo-` combo, the run SHALL be
all-or-nothing. No combo SHALL be mutated in OmniRoute without a persisted record
that makes it recoverable for rollback and visible to the `audit` stage. If any
combo in the run fails its smoke test, every combo already applied in that run
SHALL be restored to its pre-change state before the stage returns. The stage
SHALL report `apply_failed_rolled_back` (exit 6) when the partial apply is fully
rolled back, and `rollback_failed` (exit 7) when any restore call fails.

#### Scenario: Later combo failure rolls back earlier applied combos
- **GIVEN** a run that applies combo A successfully and then fails the smoke test
  on combo B
- **WHEN** the failure is handled
- **THEN** both combo A and combo B are restored to their pre-change state in
  OmniRoute
- **AND** the stage reports `apply_failed_rolled_back` (exit 6)

#### Scenario: No combo is mutated without a persisted record
- **WHEN** a combo is successfully applied in a multi-combo run
- **THEN** a persisted record for that combo exists before the next combo is
  applied, so a subsequent failure can roll it back and `audit` can see it

#### Scenario: Restore failure during partial rollback
- **GIVEN** a partial apply must be rolled back and a restore call raises
- **WHEN** the rollback runs
- **THEN** the stage reports `rollback_failed` (exit 7)

