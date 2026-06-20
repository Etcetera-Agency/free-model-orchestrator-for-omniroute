## ADDED Requirements

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
