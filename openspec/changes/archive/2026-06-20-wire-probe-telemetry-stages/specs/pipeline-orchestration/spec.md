## ADDED Requirements

### Requirement: Probe, telemetry, and quota-sync stages produce real effects

The composed runtime SHALL drive the `probing`, `telemetry-sync`, and
`quota-sync` stages through their existing domain modules and persist their real
output. The production probe adapter SHALL run only for `confirmed`-free
endpoints with reserved capacity and SHALL never exceed confirmed free capacity.
Each stage SHALL report `success` only when its declared effect is observable.

#### Scenario: Probe respects confirmed free capacity
- **WHEN** the `probing` stage runs
- **THEN** it probes only `confirmed`-free endpoints with reserved capacity
- **AND** no probe request exceeds confirmed free capacity

#### Scenario: Probe persists results and excludes failures
- **WHEN** the `probing` stage completes
- **THEN** probe results are persisted through the repository
- **AND** endpoints whose probe fails are excluded from downstream stages

#### Scenario: Telemetry sync writes normalized rows
- **WHEN** the `telemetry-sync` stage runs
- **THEN** normalized telemetry rows are persisted for use by scoring
- **AND** an adapter returning success without writing telemetry fails the suite

#### Scenario: Quota sync writes remaining-quota state
- **WHEN** the `quota-sync` stage runs
- **THEN** synced remaining-quota state is persisted with correct attribution
- **AND** an adapter returning success without writing quota state fails the suite
