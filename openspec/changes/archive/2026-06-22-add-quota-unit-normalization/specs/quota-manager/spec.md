## ADDED Requirements

### Requirement: Quota unit normalization
The system SHALL normalize heterogeneous quota axes into request-equivalents per day before comparing endpoint capacity.

#### Scenario: Request and token budgets normalize to daily requests
- **GIVEN** quota axes expressed as requests/day, requests/month, tokens/day, or tokens/month
- **WHEN** capacity is normalized
- **THEN** request axes are converted to daily requests and token axes are divided by the configured tokens-per-request factor

#### Scenario: Reactive rate gates excluded from budget capacity
- **GIVEN** quota axes expressed with minute or hour windows
- **WHEN** capacity is normalized for planning
- **THEN** those axes are excluded from the daily budget capacity

#### Scenario: Binding capacity uses tightest budget axis
- **GIVEN** multiple daily or monthly quota axes for one endpoint
- **WHEN** binding capacity is computed
- **THEN** the smallest converted request-equivalent daily value is returned

#### Scenario: Tokens-per-request config validated
- **GIVEN** startup config provides a tokens-per-request factor
- **WHEN** static config validation runs
- **THEN** non-positive factors are rejected
