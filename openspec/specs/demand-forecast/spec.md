# demand-forecast Specification

## Purpose
Define how FMO turns Hermes role consumers into protected demand for pool publication.

## Requirements

### Requirement: Demand forecasts come from Hermes consumers
The demand stage SHALL derive role demand from current Hermes consumers and
persist protected demand for pool publication.

#### Scenario: Shared combo sums demand across slots
- **WHEN** multiple consumers share one role
- **THEN** their calls are summed into the role forecast.

#### Scenario: Band is declared, not computed
- **WHEN** FMO builds demand for a role
- **THEN** quality bands remain role policy, not local endpoint scoring.

#### Scenario: Relax is delegated, not applied in FMO
- **WHEN** capacity is thin
- **THEN** FMO publishes demand and lets OmniRoute solve relaxation.

#### Scenario: Bursty weekly load
- **WHEN** weekly load is present
- **THEN** protected demand accounts for the burst window.

#### Scenario: Cold start floor applied
- **WHEN** history is missing
- **THEN** the cold-start floor prevents zero demand.

#### Scenario: Demand comes from the forecast
- **WHEN** pool specs are composed
- **THEN** role demand comes from the latest forecast.

#### Scenario: Dependency cycle
- **WHEN** demand dependencies cycle
- **THEN** the forecast rejects the cycle.

#### Scenario: Multiple agents and a shared role
- **WHEN** several agents consume the same role
- **THEN** the forecast aggregates them once per role.

#### Scenario: Reserve applied once
- **WHEN** a forecast is re-run
- **THEN** historical reserve is not compounded.

#### Scenario: Unknown new role
- **WHEN** a new role has no history
- **THEN** bootstrap demand is used.
