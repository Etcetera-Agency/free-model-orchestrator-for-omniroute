# quota-manager Specification Delta

## ADDED Requirements

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
