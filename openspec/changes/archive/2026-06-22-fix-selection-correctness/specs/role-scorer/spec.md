## ADDED Requirements

### Requirement: Production scoring derives all components from real evidence

The production `role-scoring` stage SHALL compute the weighted score from real
persisted evidence, not constant placeholders. `benchmark_fit` SHALL be derived
from `aa_subscore` over the endpoint's latest Artificial Analysis metrics;
`latency` SHALL be derived from `latency_score_source` (endpoint p95 → provider
p95 → AA latency precedence); `health` and `stability` SHALL be derived from the
endpoint's persisted `endpoint_health_observations`. When an input is genuinely
unknown the stage SHALL apply the existing uncertainty/unknown handling instead
of substituting a full `1.0`.

#### Scenario: AA quality drives the benchmark component
- GIVEN three eligible endpoints whose AA `intelligence_index` is low < mid < high
- WHEN the `role-scoring` stage computes scores
- THEN their `benchmark_fit` components are distinct and ordered low < mid < high
- AND the persisted total scores reflect that ordering

#### Scenario: Latency component uses the latency source priority
- GIVEN an endpoint with endpoint-level p95 telemetry and a provider-level p95
- WHEN the `latency` component is computed
- THEN the endpoint-level p95 is used as the latency source
- AND when only AA latency is present it is used instead of a constant

#### Scenario: Health and stability come from telemetry observations
- GIVEN one endpoint with healthy telemetry and one with degraded telemetry
- WHEN the `role-scoring` stage computes scores
- THEN the degraded endpoint's `health`/`stability` components are lower than the
  healthy endpoint's
- AND an endpoint with no telemetry does not receive a full health score

#### Scenario: Missing AA metrics apply the uncertainty penalty
- GIVEN an endpoint with no Artificial Analysis metrics for its canonical model
- WHEN its score is computed
- THEN the unknown AA subscore applies the uncertainty penalty
- AND the endpoint is not awarded a full `benchmark_fit` of 1.0
