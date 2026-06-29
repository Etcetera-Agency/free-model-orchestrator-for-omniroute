# quality-gate Specification

## Purpose
TBD - created by archiving change add-scoring. Update Purpose after archive.
## Requirements
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
- GIVEN a role gate `agentic_index >= 45` and an endpoint with `agentic_index = 30`
- WHEN eligibility runs
- THEN the endpoint is excluded from that role before weighted scoring

#### Scenario: Endpoint above the band is excluded
- GIVEN a role band `intelligence_index` with min `40` and max `60`, and an
  endpoint with `intelligence_index = 75`
- WHEN eligibility runs
- THEN the endpoint is excluded from that role as above the band
- AND an endpoint with `intelligence_index = 50` passes the band

### Requirement: Band is seed-anchored and set once

The system SHALL derive a role's quality band from the combo's seed anchor and
SHALL set it once. When the combo holds exactly one model, that model's canonical
AA metric is the anchor and the band is computed and persisted. The seed may be
represented either by a persisted provider endpoint id or by OmniRoute's
structured model step (`providerId` + `model`); both shapes SHALL resolve to the
matching canonical endpoint before deriving the anchor. Once a role has an
established band (`minimum_quality_value` set), the system SHALL keep it and
SHALL NOT re-anchor it from a seed — even if the combo is later reduced back to a
single model — so the role runs by its band and demand forecast and repeated
rebalances do not drift. Seed anchoring happens only while the band is empty
(cold start). A seed that is not confirmed-free SHALL contribute its AA metric as
the anchor only and SHALL NOT be added as a routable member.

#### Scenario: Band bounds are set once from the seed anchor
- GIVEN a combo seeded with exactly one model
- WHEN the combo is rebalanced
- THEN the role's band is derived from that model's canonical AA metric and
  persisted to `minimum_quality_value` / `maximum_quality_value`
- AND a later rebalance with several members in the combo keeps the persisted band

#### Scenario: Structured seed step anchors the band
- GIVEN a combo seeded with one structured OmniRoute model step
- WHEN the combo is rebalanced
- THEN the seed is resolved through `providerId` and `model`
- AND the role's band is derived from the matching canonical AA metric
- AND a live role id that already includes the managed `fmo-` prefix is updated
  directly, without stripping the prefix first

#### Scenario: Band capacity uses only probe-passed endpoints
- GIVEN a live seed anchor and two otherwise confirmed-free candidates
- AND one nearby candidate has a failed probe
- AND a farther candidate has a passed probe and enough capacity
- WHEN the role quality band is derived from the seed
- THEN the failed-probe candidate does not contribute capacity
- AND the band widens to include the passed candidate instead

#### Scenario: Established band is not re-anchored by a later seed
- GIVEN a role that already has an established quality band
- AND its combo is later reduced back to a single model
- WHEN the combo is rebalanced
- THEN the established band is kept and not re-anchored from the seed

#### Scenario: Paid seed anchors but is not a member
- GIVEN a combo seeded with a single model that is not confirmed-free
- WHEN the combo is rebalanced
- THEN the band anchor uses that model's AA metric
- AND the paid seed is excluded from the combo's routable members

### Requirement: Unverifiable gate handling

If the gate metric is missing for an endpoint the system SHALL set
`quality_gate_status = unverifiable` and exclude the endpoint from the role
unless `allow_unverified_quality_gate` is set. This exclusion SHALL NOT apply to
configured router endpoints (members of `auto_router_tail`): a router has no
stable underlying model, so the role quality band is inapplicable to it. A router
SHALL be exempt from the band/quality-gate filter entirely — it is neither
excluded as `unverifiable` nor ordered as a band-eligible scored member — and
SHALL remain eligible only as the combo's fallback tail.

#### Scenario: Missing gate metric
- GIVEN a role gate on `coding_index` and a non-router endpoint with no coding
  index
- WHEN the gate is evaluated and override is off
- THEN the endpoint is excluded as unverifiable

#### Scenario: Router is exempt from the band
- GIVEN a role with a quality band and a configured router endpoint that has no AA
  quality metric
- WHEN the gate is evaluated and `allow_unverified_quality_gate` is off
- THEN the router is not excluded as unverifiable
- AND it is not ordered as a band-eligible scored member
- AND it remains eligible for the combo's fallback tail

### Requirement: Index-version binding

Each gate SHALL store `metric`, `value` and `index_version` and apply only to the
matching Artificial Analysis index version. On a major index change the gate is
marked `needs_recalibration`, new allocation plans are not applied with an
unverified gate, and the previous combo is kept until thresholds update.

#### Scenario: Major index change
- GIVEN a gate bound to index version v1 and a new major index v2 arrives
- WHEN scoring runs
- THEN the v1 raw threshold is not applied to v2 and the current combo is kept
