# role-scorer Specification

## Purpose
TBD - created by archiving change add-scoring. Update Purpose after archive.
## Requirements
### Requirement: Eligibility filter precedes scoring

The system SHALL score an endpoint for a role only if it has an allowed free
access status, passed the basic probe, has sufficient usable quota greater than
zero, is matched to a canonical model, has a closed breaker, supports the role's
required capabilities, satisfies the role's context-window minimum, and passes
the role's optional quality gate. The context-window and quality-gate hard
filters SHALL be applied in the production scoring path (not only as standalone
functions), before weighted scoring. Each rejection branch SHALL expose a
distinct reason.

#### Scenario: Breaker not closed
- GIVEN an otherwise eligible endpoint whose breaker is not closed
- WHEN scoring eligibility runs
- THEN it is rejected with a breaker reason

#### Scenario: Zero quota boundary
- GIVEN an endpoint has usable quota equal to zero
- WHEN scoring eligibility runs
- THEN it is rejected with a quota reason

#### Scenario: Missing required capability
- GIVEN an endpoint lacks a role-required capability
- WHEN scoring eligibility runs
- THEN it is rejected with a capability reason

#### Scenario: Below context minimum rejected in scoring
- GIVEN an otherwise eligible endpoint whose effective context window is below
  the role minimum
- WHEN the production scoring eligibility runs
- THEN it is rejected with a context reason before weighted scoring

#### Scenario: Below quality gate rejected in scoring
- GIVEN a role with a quality gate and an otherwise eligible endpoint below it
- WHEN the production scoring eligibility runs
- THEN it is rejected with a quality-gate reason before weighted scoring

### Requirement: Additive score without price

The system SHALL compute `score = benchmark_fit + capability_fit + health +
latency + quota_headroom + stability - uncertainty`. Price SHALL NOT be a factor,
because all eligible endpoints are already free within quota.

#### Scenario: Price excluded
- GIVEN two eligible free endpoints
- WHEN they are scored
- THEN no price term influences the score

### Requirement: Artificial Analysis scoring v1

The system SHALL fetch Artificial Analysis model benchmark metadata before role
scoring unless an AA snapshot is explicitly injected by tests or offline tooling.
Because Pro-gated `GET /api/v2/language/models` is unavailable to this project,
production ingestion SHALL use the free-tier endpoint
`GET /api/v2/language/models/free`, send the configured API key in the
`x-api-key` header, fail before network I/O when the API key is missing, and
aggregate every page by following the response `pagination` (`has_more` /
`total_pages`) until no further page remains. Fetched `data` rows SHALL be
normalized into only these scoring inputs: `intelligence_index`, `coding_index`,
`agentic_index`, `median_output_tokens_per_second`, and
`median_end_to_end_seconds`, normalized to 0..1 via P5/P95 clipped min-max
(latency inverted). The end-to-end latency input SHALL be read from either
`median_end_to_end_seconds` or the free-endpoint alias
`median_end_to_end_response_time_seconds`. A missing metric SHALL NOT be treated
as 0 — its weight is redistributed and an uncertainty penalty applied; if all
three quality indices are missing the AA quality score is unknown.

#### Scenario: Artificial Analysis metadata fetch
- GIVEN role scoring has no injected AA snapshot and an AA API key is configured
- WHEN metadata sync runs before scoring
- THEN the system fetches `GET /api/v2/language/models/free` benchmark metadata
- AND sends the key in the `x-api-key` header
- AND stores the index version and normalized metric rows for scoring

#### Scenario: Artificial Analysis free-tier pagination
- GIVEN the free-tier response reports more than one page via `pagination`
- WHEN the snapshot is fetched
- THEN every page is requested in turn following `has_more`
- AND the normalized rows from all pages are combined into one snapshot

#### Scenario: Artificial Analysis API key missing
- GIVEN role scoring has no injected AA snapshot and no AA API key is configured
- WHEN metadata sync prepares the Artificial Analysis request
- THEN it fails with `aa_api_key_required`
- AND no network request is sent

#### Scenario: Artificial Analysis API key redacted
- GIVEN an AA request fails after using a configured API key
- WHEN the error is reported
- THEN the API key and full `x-api-key` header are not present in the error text

#### Scenario: End-to-end latency alias
- GIVEN a free-tier row exposes `median_end_to_end_response_time_seconds` and no `median_end_to_end_seconds`
- WHEN the row is normalized for scoring
- THEN the value is recorded as the `median_end_to_end_seconds` metric

#### Scenario: Missing metric remains missing
- GIVEN an Artificial Analysis row omits `agentic_index`
- WHEN the row is normalized for scoring
- THEN `agentic_index` remains absent
- AND it is not converted to `0`

### Requirement: Latency source priority

The system SHALL prefer OmniRoute endpoint telemetry over OmniRoute provider
telemetry over the Artificial Analysis model median for latency. If all latency
sources are missing, latency source SHALL be unknown.

#### Scenario: Endpoint telemetry available
- GIVEN both endpoint telemetry and an AA median exist
- WHEN latency is scored
- THEN endpoint telemetry is used

#### Scenario: No latency source
- GIVEN endpoint telemetry, provider telemetry and AA median are all missing
- WHEN latency source is selected
- THEN no source is selected

### Requirement: Immutable, hash-keyed scores

The system SHALL store each score immutably with an `input_state_hash` and SHALL
skip recomputation when the hash is unchanged. The score version SHALL change
when production scoring or eligibility semantics change without changing the
persisted input hash, so live runs can write new immutable scores instead of
reusing stale eligibility decisions.

#### Scenario: Unchanged inputs
- GIVEN an endpoint whose scoring inputs are unchanged
- WHEN scoring runs
- THEN no new score is computed

#### Scenario: Scoring semantics changed
- GIVEN the scorer eligibility logic changed
- AND persisted endpoint/role inputs did not change
- WHEN scoring runs with the new score version
- THEN new immutable role scores are written for the new semantics

### Requirement: Artificial Analysis fetch errors

The system SHALL treat Artificial Analysis fetch failures as metadata sync
failures for new scoring inputs. Missing API key, timeout, network failure,
non-200 status, invalid JSON, missing `intelligence_index_version`, or non-list `data` rows SHALL
produce a structured metadata error. The system SHALL NOT overwrite existing AA
scoring snapshots with invalid or partial payloads. Error output SHALL redact
API keys and `x-api-key` headers.

#### Scenario: Artificial Analysis non-200
- GIVEN the Artificial Analysis metadata request returns a non-200 status
- WHEN metadata sync runs
- THEN no new AA scoring snapshot is stored
- AND scoring continues only with previously valid data if available

#### Scenario: Artificial Analysis invalid payload
- GIVEN the Artificial Analysis response lacks `intelligence_index_version` or `data` rows
- WHEN metadata sync validates the response
- THEN the response is rejected as invalid
- AND no missing metric is synthesized as zero

### Requirement: Configured routers are not AA-scored

The system SHALL recognize an endpoint as a router when its canonical model id
matches a configured `auto_router_tail` entry `id` (provider-flexible match).
Router membership SHALL be defined by this curated config list, NOT inferred from
a naming pattern, because routers are named inconsistently (`/free`, `-auto`,
`/auto`) and their catalog cost and capabilities are unreliable defaults. Each
entry carries its own declared `input` modalities; the context window is NOT
declared in config — routers reuse the existing `effective_context_window`
computation and context-window hard filter. Catalog parent/child links SHALL NOT
be collapsed: `mimocode/mimo-auto` is matched on its own id and is not treated as
an alias of its parent `mcode/mimo-auto`.
Because a router selects its underlying model dynamically per request, it has no
stable Artificial Analysis quality band. The system SHALL NOT compute an AA
quality subscore (`benchmark_fit`) for a router and SHALL NOT apply a
missing-quality uncertainty penalty to it. A router SHALL still be subject to
every non-quality eligibility hard filter (access as free, basic probe, usable
quota, model match, closed breaker, required capabilities, context-window
minimum). The membership SHALL be exposed on the endpoint record consumed by
allocation.

#### Scenario: Configured router is recognized
- GIVEN `auto_router_tail` contains `openrouter/free`
- AND an endpoint whose canonical model is `openrouter/free`
- WHEN router membership is evaluated
- THEN the endpoint is recognized as a router
- AND the provider prefix and letter case are ignored in the match

#### Scenario: Unlisted model is not a router
- GIVEN `auto_router_tail` does not contain `google/gemini-2.5-flash`
- WHEN router membership is evaluated for that endpoint
- THEN the endpoint is not recognized as a router

#### Scenario: Child router is independent of its parent
- GIVEN `auto_router_tail` contains `mimocode/mimo-auto` but not its catalog
  parent `mcode/mimo-auto`
- WHEN router membership is evaluated for both endpoints
- THEN only `mimocode/mimo-auto` is recognized as a router
- AND the parent link is not used to collapse or alias the two

#### Scenario: Router skips AA quality scoring
- GIVEN an eligible router endpoint with no AA quality indices
- WHEN role scoring runs
- THEN no `benchmark_fit` term is contributed
- AND no missing-quality uncertainty penalty is applied

#### Scenario: Router still honors non-quality filters
- GIVEN a router endpoint whose breaker is not closed
- WHEN scoring eligibility runs
- THEN it is rejected with a breaker reason like any other endpoint

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
