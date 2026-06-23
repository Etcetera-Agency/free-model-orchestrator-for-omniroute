## MODIFIED Requirements

### Requirement: Apply stage derives quota and probe safety from persisted state

The production `apply` stage SHALL compute the `quota_safe` and `probes_passed`
apply-precondition inputs from persisted repository state for the endpoints in
the combos it is about to apply, and SHALL NOT use hardcoded values. `quota_safe`
SHALL be true for an endpoint only when it is confirmed-free, hard-stop-capable,
has a fresh passing probe, has a **known daily budget** — a research/calibration
capacity in request-equivalents per day above the safety buffer — and a **fresh
live liveness signal** showing `percentRemaining` above the configured floor
(`APPLY_MIN_PERCENT_REMAINING`) and not currently locked out. The learned live
request rate (`quotaTotal`/`quotaUsed`) is a sub-day reactive gate enforced by
OmniRoute and SHALL NOT be used as the daily-budget capacity. The safety buffer
SHALL be a configured positive floor, not an implicit `0`. Liveness SHALL come
from a live quota observation, not from a value assumed at classification time: an
assumed remaining synthesized at classification without any live observation SHALL
NOT satisfy `quota_safe`. A future `resetAt` SHALL mean the endpoint is currently
locked out and excluded; a null `resetAt` SHALL NOT by itself fail the gate (it is
the healthy, not-rate-limited state). `probes_passed` SHALL be true only when
every endpoint in the desired combos has a passing, non-stale probe/smoke result.
The evaluation SHALL fail closed: any missing, unknown, assumed, stale, exhausted,
or locked-out input yields the corresponding value `False`, the stage returns
`unsafe_to_apply` (exit 5), and no combo is mutated.

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
- **WHEN** every endpoint in the desired combos is confirmed-free, hard-stop,
  freshly probed, has a known daily budget above the buffer, and a fresh liveness
  signal above the floor that is not locked out
- **THEN** both derived inputs are `True`
- **AND** the apply stage proceeds to mutate the combos

#### Scenario: Assumed remaining does not satisfy the apply gate
- **WHEN** an endpoint's only quota evidence is an assumed remaining synthesized
  at classification time, with no live liveness observation
- **THEN** the stage derives `quota_safe` as `False` for that endpoint
- **AND** the stage returns `unsafe_to_apply` (exit 5) and mutates no combo

#### Scenario: Zero safety buffer does not satisfy the apply gate
- **WHEN** an endpoint's daily-budget record carries no safety buffer and its
  capacity does not exceed the configured minimum buffer
- **THEN** the stage treats the buffer as the configured positive floor, not `0`
- **AND** derives `quota_safe` as `False` rather than passing on a zero buffer

#### Scenario: Research budget with healthy liveness passes
- **WHEN** a confirmed-free, hard-stop, freshly probed endpoint has a
  research/calibration daily budget above the buffer and a fresh `percentRemaining`
  above the floor that is not locked out
- **THEN** the stage derives `quota_safe` as `True`
- **AND** the apply stage proceeds to mutate the combos

#### Scenario: Exhausted or locked-out endpoint is excluded
- **WHEN** an endpoint's fresh liveness shows `percentRemaining` at or below the
  floor, or its `resetAt` is in the future
- **THEN** the stage derives `quota_safe` as `False` for that endpoint
- **AND** the stage returns `unsafe_to_apply` (exit 5) and mutates no combo

#### Scenario: Endpoint with null reset is not rejected
- **WHEN** a confirmed-free, hard-stop, freshly probed endpoint has a known daily
  budget, healthy liveness, and `resetAt = null`
- **THEN** the null `resetAt` does not fail the gate
- **AND** the stage derives `quota_safe` as `True`
