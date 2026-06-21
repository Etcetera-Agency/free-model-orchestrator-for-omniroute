# quality-gate Specification

## MODIFIED Requirements

### Requirement: Single optional gate as hard pre-filter

The system SHALL support one quality band per role: a `metric` in
`intelligence_index | coding_index | agentic_index` with a lower bound
(`minimum_quality_value`) and an optional upper bound (`maximum_quality_value`).
It SHALL apply the band as a hard filter before weighted scoring: an endpoint is
eligible for the role only when `minimum_quality_value ≤ metric ≤
maximum_quality_value`. When `maximum_quality_value` is NULL the band degrades to
the previous min-only behavior. Weighted scoring only orders endpoints that
passed the band.

#### Scenario: Below the gate
- GIVEN a role band `agentic_index` with min `45` and an endpoint with
  `agentic_index = 30`
- WHEN eligibility runs
- THEN the endpoint is excluded from that role before weighted scoring

#### Scenario: Endpoint above the band is excluded
- GIVEN a role band `intelligence_index` with min `40` and max `60`, and an
  endpoint with `intelligence_index = 75`
- WHEN eligibility runs
- THEN the endpoint is excluded from that role as above the band
- AND an endpoint with `intelligence_index = 50` passes the band

## ADDED Requirements

### Requirement: Band is seed-anchored and set once

The system SHALL derive a role's quality band from the combo's seed anchor and
SHALL set it once. When the combo holds exactly one model, that model's canonical
AA metric is the anchor and the band is computed and persisted. When the combo
already holds more than one model and a band is persisted, the system SHALL keep
the persisted band rather than re-deriving it, so repeated rebalances do not
drift. Stripping the combo back to a single model SHALL re-anchor the band on the
next run. A seed that is not confirmed-free SHALL contribute its AA metric as the
anchor only and SHALL NOT be added as a routable member.

#### Scenario: Band bounds are set once from the seed anchor
- GIVEN a combo seeded with exactly one model
- WHEN the combo is rebalanced
- THEN the role's band is derived from that model's canonical AA metric and
  persisted to `minimum_quality_value` / `maximum_quality_value`
- AND a later rebalance with several members in the combo keeps the persisted band

#### Scenario: Re-seeding re-anchors the band
- GIVEN a combo whose members are reduced back to a single model
- WHEN the combo is rebalanced
- THEN the band is re-derived from the remaining model's AA metric

#### Scenario: Paid seed anchors but is not a member
- GIVEN a combo seeded with a single model that is not confirmed-free
- WHEN the combo is rebalanced
- THEN the band anchor uses that model's AA metric
- AND the paid seed is excluded from the combo's routable members
