# quota-manager Specification

## Purpose
TBD - created by archiving change add-quota. Update Purpose after archive.
## Requirements
### Requirement: Effective remaining counter

The system SHALL compute effective remaining quota from live counters, recent
attribution and reservations. If every counter source is unknown, effective
remaining SHALL be unknown. Pending reservations and safety buffer MAY make
effective remaining negative; that result SHALL be preserved.

#### Scenario: No reliable counter
- GIVEN no reliable live, attributed or reserved counter exists
- WHEN effective remaining is computed
- THEN the result is unknown

#### Scenario: Negative effective remaining
- GIVEN pending reservations plus safety buffer exceed remaining quota
- WHEN effective remaining is computed
- THEN the negative value is returned

### Requirement: Hard-stop gating

The system SHALL require provider hard-stop semantics before treating free quota
as usable.

#### Scenario: No hard stop
- GIVEN a provider has free quota but no confirmed hard stop
- WHEN quota is evaluated for allocation
- THEN the endpoint is rejected

#### Scenario: Hard stop false
- GIVEN `require_hard_stop(False)` is called
- WHEN validation runs
- THEN it raises `ValueError`

### Requirement: Reservation only for own probes

The system SHALL reserve quota only for its own probes; production traffic flows
through OmniRoute and requires no per-request reservation by the orchestrator.

#### Scenario: Production request
- GIVEN production traffic uses a combo
- WHEN the orchestrator plans capacity
- THEN it does not reserve quota per production request

### Requirement: Reset handling

After a reset the system SHALL NOT blindly zero counters; it SHALL request live
quota, update counters, reclassify access, and only then allow probing.

#### Scenario: After reset
- GIVEN a quota pool just reset
- WHEN the manager processes it
- THEN it fetches live quota and reclassifies before any probe

### Requirement: Historical reserve guard

The system SHALL reject any forecast record marked as using a historical source
without the configured historical reserve (`historical_reserve_multiplier`)
applied.

#### Scenario: Missing reserve
- GIVEN a record flagged historical-source but without the reserve applied
- WHEN the manager validates it
- THEN the record is rejected

### Requirement: Live quota source fetch

The system SHALL fetch live quota (limit, remaining, reset) during quota reset
and reclassification from OmniRoute `GET /api/usage/quota` (or the configured
provider's own quota surface), unless quota values are explicitly injected. The
fetch SHALL use configured credentials with bounded retries and structured
errors. When the quota source is unavailable or returns stale data (beyond the
configured freshness window), the system SHALL fail closed — it SHALL NOT infer
usable capacity from missing or stale quota.

#### Scenario: Quota fetched at reset
- GIVEN a quota reset window is reached and no quota values are injected
- WHEN reclassification runs
- THEN current quota is fetched from the configured source
- AND effective-remaining is recomputed from the fetched values

#### Scenario: Quota source unavailable
- GIVEN the quota source is unavailable or returns stale data
- WHEN reclassification runs
- THEN no usable capacity is inferred
- AND the endpoint is excluded or degraded rather than treated as free

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
