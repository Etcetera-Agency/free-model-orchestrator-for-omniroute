# allocator Specification

## ADDED Requirements

### Requirement: Global allocation before combos

The system SHALL allocate the usable capacity of all quota pools across all roles
globally before building any combo, so the same endpoint/account cannot be
counted as guaranteed capacity for several roles at once.

#### Scenario: Shared endpoint across roles
- GIVEN one endpoint eligible for three roles
- WHEN allocation runs
- THEN its quota is not promised in full to all three roles simultaneously

### Requirement: Hard constraints and heavy-role separation

The system SHALL enforce per-pool and per-provider-group caps and SHALL NOT make
`research_scout`, `health_reasoning` and `cross_domain_orchestrator` primary in
the same quota pool.

#### Scenario: Two heavy roles, one pool
- GIVEN `research_scout` and `health_reasoning` both prefer pool G as primary
- WHEN allocation runs
- THEN they do not both take G as primary

### Requirement: Oversubscription gate

The system SHALL compute `oversubscription_ratio` per pool after shared-role
expansion and SHALL NOT apply a plan where any pool ratio exceeds 1.

#### Scenario: Oversubscribed pool
- GIVEN projected guaranteed+opportunistic usage exceeds usable capacity for a pool
- WHEN the plan is validated
- THEN the plan is not applied

### Requirement: One priority combo per role, no weights

The system SHALL emit exactly one combo per role as an ordered endpoint list with
`strategy = priority` (index 0 = primary, 1..N = fallback); endpoint weights SHALL
NOT be calculated or stored.

#### Scenario: Combo output
- GIVEN an allocated role
- WHEN its combo is emitted
- THEN it is an ordered priority list with no weights

### Requirement: Degraded modes, no paid fallback

The system SHALL mark a role `unavailable`, `degraded_single_provider`,
`degraded_low_quota` or `degraded_quality_capacity` rather than create a paid
fallback when capacity is insufficient.

#### Scenario: Insufficient free capacity
- GIVEN a role with no sufficient free capacity
- WHEN allocation runs
- THEN the role is marked degraded and no paid endpoint is added

### Requirement: Stability

The system SHALL NOT reorder or rebuild a combo when the eligible set is
unchanged, score movement does not cross the reorder threshold, improvement is
below threshold, or a new endpoint has not passed its stability period.

#### Scenario: Trivial score drift
- GIVEN scores moved less than the reorder threshold
- WHEN the daily run builds combos
- THEN the existing combo order is kept
