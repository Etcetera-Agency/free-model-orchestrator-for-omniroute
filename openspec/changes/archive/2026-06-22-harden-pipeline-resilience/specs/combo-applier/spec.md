## MODIFIED Requirements

### Requirement: Apply stage derives quota and probe safety from persisted state

The production `apply` stage SHALL compute the `quota_safe` and `probes_passed`
apply-precondition inputs from persisted repository state for the endpoints in
the combos it is about to apply, and SHALL NOT use hardcoded values. `quota_safe`
SHALL be true only when every endpoint in the desired combos has a current
quota-safety record with confirmed hard-stop behavior and remaining capacity
above the safety buffer. The safety buffer SHALL be a configured positive floor,
not an implicit `0`: a record that carries no buffer SHALL be treated as having
the configured minimum buffer, not zero. The remaining capacity SHALL be a
live-observed value; an assumed remaining (e.g. one synthesized equal to the
quota limit at classification time, without a live quota observation) SHALL NOT
satisfy `quota_safe`. `probes_passed` SHALL be true only when every endpoint
in the desired combos has a passing, non-stale probe/smoke result. The evaluation
SHALL fail closed: any missing, unknown, assumed, or stale input yields the
corresponding value `False`, the stage returns `unsafe_to_apply` (exit 5), and no
combo is mutated.

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

#### Scenario: Assumed remaining does not satisfy the apply gate
- **WHEN** an endpoint's only quota evidence is an assumed remaining synthesized
  at classification time, with no live quota observation
- **THEN** the stage derives `quota_safe` as `False` for that endpoint
- **AND** the stage returns `unsafe_to_apply` (exit 5) and mutates no combo

#### Scenario: Zero safety buffer does not satisfy the apply gate
- **WHEN** an endpoint's quota record carries no safety buffer and its remaining
  does not exceed the configured minimum buffer
- **THEN** the stage treats the buffer as the configured positive floor, not `0`
- **AND** derives `quota_safe` as `False` rather than passing on a zero buffer
