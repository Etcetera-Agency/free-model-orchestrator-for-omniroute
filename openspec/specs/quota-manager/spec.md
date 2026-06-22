# quota-manager Specification

## Purpose
TBD - created by archiving change add-quota. Update Purpose after archive.
## Requirements
### Requirement: Effective remaining counter

The system SHALL compute effective remaining quota, in request-equivalents per
day, from live counters, recent attribution and reservations, using the
converted limit from the endpoint's binding capacity. If every counter source is
unknown, effective remaining SHALL be unknown. Pending reservations and safety
buffer MAY make effective remaining negative; that result SHALL be preserved.

#### Scenario: No reliable counter
- GIVEN no reliable live, attributed or reserved counter exists
- WHEN effective remaining is computed
- THEN the result is unknown

#### Scenario: Negative effective remaining
- GIVEN pending reservations plus safety buffer exceed remaining quota
- WHEN effective remaining is computed
- THEN the negative value is returned

#### Scenario: Remaining expressed in request-equivalents per day
- GIVEN an endpoint whose binding capacity comes from a token budget
- WHEN effective remaining is computed
- THEN the result is in request-equivalents per day, not raw tokens

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

### Requirement: Capacity bound across axes in request-equivalents per day

The system SHALL assemble each endpoint's known budget axes — from its research
rule, its no-auth calibration rule and its live quota — as a list of
`(metric, window, amount)` and convert them into a single capacity in
request-equivalents per day using `binding_capacity` with the configured
`tokens_per_request` factor, bound by the tightest axis. Token axes SHALL be
converted by the factor; request day/month axes SHALL pass through; sub-day request
windows SHALL be excluded as reactive rate gates. Live quota (`GET
/api/usage/quota`, `quotaTotal`/`quotaUsed`) SHALL be treated as the `tokens` axis
it is. The no-auth calibration rule SHALL be included in the axis list, not only
research and live.

#### Scenario: Tightest axis binds the capacity
- GIVEN an endpoint with a `tokens/month` live budget and a `requests/day` research
  limit
- WHEN its capacity is computed
- THEN it is one value in request-equivalents per day equal to the tighter
  converted axis

#### Scenario: Live token budget converted
- GIVEN live quota reports `quotaTotal`/`quotaUsed` token counts
- WHEN capacity is computed
- THEN the token limit is converted to request-equivalents per day via the factor

#### Scenario: Calibrated endpoint contributes its axis
- GIVEN a self-calibrated no-auth `tokens` rule for an endpoint
- WHEN its capacity is computed
- THEN the calibration axis is included and converted

#### Scenario: Sub-day request axis excluded
- GIVEN an endpoint that also carries a `requests/minute` axis
- WHEN its binding capacity is computed
- THEN the sub-day request axis is excluded

### Requirement: Weekly recalibration of the global tokens-per-request factor

The system SHALL maintain a single global `tokens_per_request` factor used to
convert token budgets to request-equivalents per day. On a weekly cadence it SHALL
refine that factor from accumulated no-auth calibration observations
(`observed_tokens`, `observed_requests`) by dividing total observed tokens by
total observed requests. The refinement SHALL keep the current factor unchanged
when the total observed requests are below the configured minimum, and SHALL clamp
any change to within the configured maximum ratio of the current factor so a
single noisy period cannot swing the factor that every derived endpoint depends
on. The factor SHALL stay positive.

#### Scenario: Factor refined from observations
- GIVEN calibration observations totalling 1,500,000 tokens over 1,000 requests
- AND a current factor of 2000
- WHEN weekly recalibration runs
- THEN the refined factor is 1500

#### Scenario: Too little signal keeps the current factor
- GIVEN total observed requests below the configured minimum
- WHEN weekly recalibration runs
- THEN the factor is left unchanged

#### Scenario: A noisy week is clamped
- GIVEN observations that would imply a factor far below the current value
- WHEN weekly recalibration runs
- THEN the new factor is clamped to the configured maximum downward change from the
  current factor

### Requirement: Recompute only self-derived capacities

After the global factor is refined, the system SHALL recompute request-equivalent
capacity only for endpoints whose quota was self-derived — source `summary`
(search) or `calibrated` (self-calculated). Endpoints backed by an authoritative
live quota SHALL NOT be recomputed. The refined factor and the recomputed
derived capacities SHALL be persisted together so they are always mutually
consistent.

#### Scenario: Derived endpoints recomputed, live untouched
- GIVEN a `summary` endpoint, a `calibrated` endpoint and a `live` endpoint
- WHEN the factor is refined and recomputation runs
- THEN the `summary` and `calibrated` endpoints get new req/day capacities under
  the refined factor
- AND the `live` endpoint is not recomputed

#### Scenario: Factor and capacities persisted consistently
- GIVEN a recalibration run refines the factor
- WHEN it persists results
- THEN the stored factor and the stored derived capacities are written in one
  transaction and reflect the same factor value
