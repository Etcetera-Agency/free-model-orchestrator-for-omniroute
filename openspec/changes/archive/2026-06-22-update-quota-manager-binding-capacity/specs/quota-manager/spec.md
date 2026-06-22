# quota-manager Specification Delta

## ADDED Requirements

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

## MODIFIED Requirements

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
