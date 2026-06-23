## MODIFIED Requirements

### Requirement: Live quota source fetch

The system SHALL fetch live quota (limit, remaining, reset) during quota reset
and reclassification from OmniRoute `GET /api/usage/quota` (or the configured
provider's own quota surface), unless quota values are explicitly injected. The
fetch SHALL use configured credentials with bounded retries and structured
errors. The system SHALL capture the live **liveness** signal independently of
daily-budget capacity: `percentRemaining` and a lockout flag derived from
`resetAt` (a `resetAt` strictly in the future means the connection is currently
rate-limited and SHALL be treated as locked out; a null `resetAt` is the healthy,
not-missing state). The learned `quotaTotal`/`quotaUsed` SHALL be treated as
**request counts for a sub-day rate window** (a reactive rate), NOT as a token
budget and NOT as a daily-budget absolute; a null `quotaTotal` SHALL yield
liveness without any learned rate rather than a zero capacity. When the quota
source is unavailable or returns stale data (beyond the configured freshness
window), the system SHALL fail closed — it SHALL NOT infer usable capacity from
missing or stale quota.

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

#### Scenario: Percent-remaining and lockout captured from live quota
- GIVEN a live quota entry with `percentRemaining` and a `resetAt` in the future
- WHEN the quota snapshot is normalized
- THEN `percentRemaining` is captured as the liveness signal
- AND the entry is marked locked out

#### Scenario: Learned request limit captured as a reactive rate, not a daily budget
- GIVEN a live quota entry whose learned `quotaTotal`/`quotaUsed` are request
  counts for a sub-day window
- WHEN the quota snapshot is normalized
- THEN they are captured as a reactive request rate
- AND they are NOT divided by `tokens_per_request` and NOT added to the daily
  budget

#### Scenario: Idle provider yields liveness without an authoritative absolute
- GIVEN a live quota entry with `quotaTotal: null`, `percentRemaining: 100`,
  `resetAt: null`
- WHEN the quota snapshot is normalized
- THEN the entry carries a healthy, not-locked-out liveness signal
- AND it carries no learned rate rather than a zero capacity

### Requirement: Capacity bound across axes in request-equivalents per day

The system SHALL assemble each endpoint's known budget axes — from its research
rule and its no-auth calibration rule — as a list of `(metric, window, amount)`
and convert them into a single capacity in request-equivalents per day using
`binding_capacity` with the configured `tokens_per_request` factor, bound by the
tightest axis. Token axes SHALL be converted by the factor; request day/month
axes SHALL pass through; sub-day request windows SHALL be excluded as reactive
rate gates. Live quota (`GET /api/usage/quota`, `quotaTotal`/`quotaUsed`) is a
**request count for a sub-day rate window**, so it SHALL be excluded from the
binding daily budget as a reactive rate gate — it SHALL NOT be converted as a
`tokens` axis. The no-auth calibration rule SHALL be included in the axis list,
not only research.

#### Scenario: Tightest axis binds the capacity
- GIVEN an endpoint with a `tokens/month` research budget and a `requests/day`
  research limit
- WHEN its capacity is computed
- THEN it is one value in request-equivalents per day equal to the tighter
  converted axis

#### Scenario: Live quota requests do not contribute to the daily budget
- GIVEN live quota reports `quotaTotal`/`quotaUsed` request counts for a sub-day
  window
- WHEN the daily budget capacity is computed
- THEN the live request rate is excluded as a reactive rate gate
- AND it is not converted to request-equivalents per day as a token axis

#### Scenario: Calibrated endpoint contributes its axis
- GIVEN a self-calibrated no-auth `tokens` rule for an endpoint
- WHEN its capacity is computed
- THEN the calibration axis is included and converted

#### Scenario: Sub-day request axis excluded
- GIVEN an endpoint that also carries a `requests/minute` axis
- WHEN its binding capacity is computed
- THEN the sub-day request axis is excluded
