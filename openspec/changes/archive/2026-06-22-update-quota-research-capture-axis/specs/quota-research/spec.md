# quota-research Specification Delta

## ADDED Requirements

### Requirement: Summary extraction captures the present quota axis

The deterministic summary extraction SHALL set the claim metric from the axis the
summary text actually expresses — `tokens` or `requests` — rather than a fixed
metric. It SHALL recognise token phrasing (`N tokens per day/month`) as well as
request phrasing (`N requests per day/month`). When the summary expresses both a
request limit and a token limit, both axes SHALL be captured so the normalizer can
bind the tighter one. The deterministic validator, `summary_confidence_cap` and
the worsen-quota safe-mode rule remain the source of truth for every captured
axis.

#### Scenario: Token budget summary
- GIVEN a summary stating a limit of N tokens per month with a hard stop
- WHEN the deterministic summary claim is extracted
- THEN the claim metric is `tokens` with that amount and the `month` window

#### Scenario: Request limit summary unchanged
- GIVEN a summary stating a limit of N requests per day
- WHEN the deterministic summary claim is extracted
- THEN the claim metric is `requests` with that amount and the `day` window

#### Scenario: Both axes present
- GIVEN a summary stating both a requests-per-day and a tokens-per-month limit
- WHEN the summary claim is extracted
- THEN both a `requests/day` axis and a `tokens/month` axis are captured

### Requirement: Sub-day request rates are reactive, not budget rules

The system SHALL treat a sub-day request rate (`requests` with window `minute` or
`hour`) as a reactive rate gate policed by OmniRoute and SHALL NOT activate it as a
capacity rule. When a sub-day request rate is the only signal, the endpoint SHALL
remain without a confirmed budget rule. This routing SHALL apply identically to
deterministic-summary claims and to Instructor-inspector claims; otherwise an
inspector-returned `metric` SHALL be carried through unchanged.

#### Scenario: Requests-per-minute only does not activate
- GIVEN a summary expressing only N requests per minute
- WHEN extraction runs
- THEN no capacity rule is activated and the endpoint stays without a confirmed
  budget rule

#### Scenario: Inspector token claim carried through
- GIVEN the Instructor inspector returns a claim with metric `tokens`
- WHEN the claim is activated
- THEN the metric is carried through unchanged and capped by `summary_confidence_cap`

#### Scenario: Inspector sub-day request claim routed out
- GIVEN the Instructor inspector returns a `requests` claim with a `minute` window
- WHEN the claim is processed
- THEN it is not activated as a capacity rule
