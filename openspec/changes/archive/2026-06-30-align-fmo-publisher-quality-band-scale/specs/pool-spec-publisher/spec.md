# pool-spec-publisher Specification

## MODIFIED Requirements

### Requirement: Publisher fills only FMO-owned fields

The system SHALL fill only the contract fields it owns: `pool_id`, `combo_id`,
`demand` (`requests_per_day`, `consumers`, `workload_class`), and `constraints`
(`free_only`, `capabilities`, `min_context_tokens`, `quality_band` intent), and the
`tail` reference. The system SHALL declare `workload_class` qualitatively from the
contract vocabulary (`light`, `chat`, `reasoning`, `tools`) and SHALL NOT emit an
off-vocabulary class such as `standard`; an unmapped or legacy class SHALL be mapped to
the agreed default. The system SHALL emit the `quality_band` `min` and `max` as
normalized scores in `[0..1]` on OmniRoute's `model_intelligence.score` scale, SHALL NOT
pass through a 0-100 or ELO-scaled value, and SHALL NOT default `max` to a value outside
`[0..1]`. The system SHALL NOT compute a token count, model score, model match, live
quota, or candidate capacity.

#### Scenario: Demand from forecast, consumers from inventory
- GIVEN aggregated demand for a role and its distinct consumer count
- WHEN the pool is composed
- THEN `demand.requests_per_day` comes from the demand forecast
- AND `demand.consumers` comes from the Hermes inventory

#### Scenario: No capacity computation
- WHEN a pool is composed
- THEN the publisher does not read candidate capacity, live quota, or model scores

#### Scenario: Quality band emitted on the normalized scale
- GIVEN a role whose quality intent is expressed on a 0-100 or ELO scale
- WHEN the pool is composed
- THEN `quality_band.min` and `quality_band.max` are emitted within `[0..1]`
- AND no value outside `[0..1]` is published

#### Scenario: workload_class stays in the contract vocabulary
- GIVEN a role with a legacy or missing `workload_class`
- WHEN the pool is composed
- THEN `demand.workload_class` is one of `light`, `chat`, `reasoning`, `tools`
- AND a legacy value such as `standard` is mapped to the agreed default
