## ADDED Requirements

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
