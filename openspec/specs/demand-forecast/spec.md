# demand-forecast Specification

## Purpose
TBD - created by archiving change add-allocation. Update Purpose after archive.
## Requirements
### Requirement: Aggregate demand per reset horizon

The system SHALL aggregate role demand by summing all agent→role bindings and
expanding shared-role dependencies as a directed acyclic graph, computed over the
horizon to each quota pool's reset. Dependency cycles SHALL be rejected.

#### Scenario: Multiple agents and a shared role
- GIVEN agents A, B, C call `research_scout` 20/10/5 times and each call triggers 3 `fetch` calls
- WHEN demand is aggregated
- THEN `research_scout` demand is 35 and `fetch` dependency demand is 105

#### Scenario: Dependency cycle
- GIVEN a dependency graph `fetch → research_scout → fetch`
- WHEN validation runs
- THEN the graph is rejected

### Requirement: Expected and protected demand

The system SHALL compute both expected demand and protected demand (the max of
the p95 forecast and expected×peak-multiplier), tracked separately for requests
and tokens. Guaranteed budgets SHALL be built from protected demand.

#### Scenario: Bursty weekly load
- GIVEN a role with low average but a weekly burst
- WHEN demand is computed
- THEN protected demand reflects the burst, not just the average

### Requirement: One-time historical reserve

The system SHALL multiply any history-based forecast by the configured
`historical_reserve_multiplier` exactly once (applied after window normalization,
before allocation) and record base value, multiplier and reserved value.

#### Scenario: Reserve applied once
- GIVEN a historical forecast feeding several aggregation layers
- WHEN the reserve is applied
- THEN it is applied exactly once and recorded

### Requirement: Cold start never yields zero

The system SHALL never produce zero demand for an enabled role. Source priority
is exact schedule, then bootstrap profile, then role bootstrap, then global
fallback; an entirely unknown workload gets the minimum role budget with the
cold-start safety multiplier and low confidence. Transition to history is blended
and only after representative samples.

#### Scenario: Unknown new role
- GIVEN an enabled role with no schedule, config or history
- WHEN demand is computed
- THEN it receives the minimum role budget with the cold-start multiplier, not zero

