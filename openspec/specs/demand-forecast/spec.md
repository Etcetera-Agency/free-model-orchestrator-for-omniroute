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

### Requirement: Allocation demand is forecast-derived in production

The production allocation path SHALL compute demand through `forecast` —
aggregate demand per reset horizon, expected and protected demand, the one-time
historical reserve, and the cold-start floor — and feed it into the global
allocator. The direct `expected_load["requests"]` shortcut SHALL be removed. The
no-paid-fallback invariant and deterministic ordering remain unchanged.

#### Scenario: Demand comes from the forecast
- **WHEN** the allocation stage runs
- **THEN** per-role demand is produced by `forecast`
- **AND** an allocation reading `expected_load["requests"]` directly fails the suite

#### Scenario: Cold start floor applied
- **WHEN** an unknown new role is allocated
- **THEN** its demand is at least the cold-start floor (never zero)

#### Scenario: Reserve applied once
- **WHEN** the one-time historical reserve is consumed for a role
- **THEN** it is not re-applied on subsequent runs

### Requirement: Shared combo demand sums across slots

The system SHALL sum the `calls_per_run` of every Hermes slot that routes to the
same OmniRoute combo — main or auxiliary, in the same or different profiles —
into that combo's aggregated demand, so a shared combo's forecast reflects total
load rather than any single referencing slot.

#### Scenario: Shared combo sums demand across slots
- GIVEN two profiles whose auxiliary `vision` slots both point at combo `C`
- WHEN demand is aggregated
- THEN combo `C`'s demand is the sum of both slots' `calls_per_run`
- AND a third profile routing its main combo to `C` adds its load to the same sum

### Requirement: Quality band widens to cover protected demand

The system SHALL size a combo's quality band from the forecast: starting at the
seed anchor, the band widens (down to an adequacy floor, and upward without a
fixed ceiling) until the confirmed-free capacity of in-band endpoints covers the
role's `protected_requests`. The seed anchor may therefore sit anywhere within
the resulting band. When in-band confirmed-free capacity cannot cover protected
demand even at the floor, the role SHALL be marked `degraded` rather than
admitting below-floor or paid capacity.

#### Scenario: Quality band widens to cover protected demand
- GIVEN a seed anchor and a `protected_requests` larger than the anchor model's
  free capacity alone
- WHEN the band is computed
- THEN the band widens around the anchor to include enough confirmed-free in-band
  capacity to cover protected demand
- AND when even the widest in-band free capacity is insufficient the role is
  marked `degraded`, not filled with below-floor or paid endpoints
