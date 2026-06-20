## ADDED Requirements

### Requirement: Forecast and lifecycle run before allocation

The pipeline SHALL run role-lifecycle reconciliation and demand forecasting
before allocation so that allocation operates over a reconciled role set with
forecast-derived demand. These steps SHALL be deterministic and SHALL produce
observable persisted effects.

#### Scenario: Reconcile and forecast precede allocation
- **WHEN** a `full` run executes
- **THEN** role-lifecycle reconcile and demand forecast complete before allocation
- **AND** allocation consumes the reconciled roles and forecast demand
