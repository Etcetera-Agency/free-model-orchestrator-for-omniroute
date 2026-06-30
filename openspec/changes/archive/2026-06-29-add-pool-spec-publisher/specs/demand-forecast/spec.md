# demand-forecast Specification

## MODIFIED Requirements

### Requirement: Quality band widens to cover protected demand

The system SHALL declare a per-pool quality band as a **policy intent**, not a
capacity-derived range. The band carries `category`, `min`, `max`, and a `relax`
intent (`when: underfilled`, `max_delta`) expressed against OmniRoute's
`model_intelligence.score`. The system SHALL NOT read candidate capacity,
confirmed-free status, or model scores to widen the band, and SHALL NOT mark a role
`degraded` from a capacity calculation. OmniRoute resolves the band against
`model_intelligence`, fills the head toward demand, and applies the declared `relax`
when a pool is underfilled.

#### Scenario: Band is declared, not computed
- GIVEN a role quality policy with `category`, `min`, `max`, and `relax`
- WHEN the pool spec is composed
- THEN the quality band is taken from the role policy verbatim
- AND no confirmed-free capacity or candidate score is read to size it

#### Scenario: Relax is delegated, not applied in FMO
- GIVEN a declared band with a `relax.max_delta`
- WHEN the generation is published
- THEN FMO does not widen the band itself
- AND OmniRoute applies the relax when the pool is underfilled
