# quota-research Specification

## Purpose
TBD - created by archiving change add-quota. Update Purpose after archive.
## Requirements
### Requirement: Primary quota source where OmniRoute is silent

The system SHALL use quota research as the primary source of quota for any
endpoint not covered by an official quota API or by OmniRoute (the free registry
and rate-limits cover only a subset of providers). It SHALL NOT re-search daily
an endpoint whose free access is already confirmed and whose rule is not stale.

Quota research SHALL run only when triggered by a free-model change since the
prior run, restricted to models reachable through an existing OmniRoute
connection: either a newly detected confirmed-free model (models.dev
`free`/`0-cost` or free-provider), or an existing model whose free/0-cost status
changed in either direction (free to paid, paid to free, 0-cost to priced). When
no such change is detected, the stage is a no-op for that run; the daily live
quota/probe/health path is unaffected. When triggered, the system SHALL perform
a full recalc that re-verifies every provider/account quota pool, overriding the
not-stale daily skip for that run, because one free-model change is a signal
that other provider policies may also have changed. OmniRoute `quotaTotal`
(`GET /api/usage/quota`), where present, SHALL be used as the known-limit input;
search SHALL still establish hard-stop behaviour for each provider/account
quota pool. Provider/account recalc SHALL persist provider-wide rules with
`model_pattern = '*'`; exact endpoint/model rules are reserved for explicit
endpoint-filtered research. Provider/account search SHALL first establish quota
topology: provider/account-wide, model-group/per-model, RPM-only, or unknown.
The system SHALL NOT widen a model-group/per-model quota into a provider/account
wildcard rule.

#### Scenario: Endpoint absent from OmniRoute registry
- GIVEN an endpoint with no confirmed quota from any official API or OmniRoute
- WHEN the daily batch reaches quota research during a triggered recalc
- THEN that endpoint is researched to obtain a rule

#### Scenario: No new free model skips quota research
- GIVEN no free-model change (no new model and no free/0-cost status change) since
  the prior run
- WHEN the pipeline reaches quota research
- THEN the stage performs no `/v1/search` and reports an idempotent no-change
- AND the live quota/probe/health daily path still runs

#### Scenario: Changed free status triggers recalc
- GIVEN an existing model whose free/0-cost status changed since the prior run
  (free to paid or paid to free), reachable via an existing connection
- WHEN free-model-change detection runs
- THEN a full recalc is triggered and all affected provider/account quota pools
  are re-searched

#### Scenario: Provider account recalc researches one quota pool
- GIVEN a new confirmed-free model reachable via an existing connection
- WHEN quota research runs
- THEN each provider/account quota pool is searched once (the not-stale daily
  skip is overridden)
- AND the search query asks for quota topology before numeric quota extraction
- AND the resulting quota rule is provider-wide for that account
- AND an OmniRoute-known `quotaTotal` is used as the limit while search sets
  hard-stop behaviour

#### Scenario: Model-group topology is not widened to provider wildcard
- GIVEN provider/account research finds that quota differs by model group or
  concrete model
- WHEN quota research evaluates the provider/account result
- THEN no provider/account wildcard rule is written
- AND the provider remains fail-closed until group-specific or endpoint-specific
  research records the narrower rule

#### Scenario: Endpoint filter researches one endpoint
- GIVEN multiple endpoints need quota research during a triggered recalc
- WHEN quota research is run with a specific endpoint id or provider model id
- THEN only that endpoint is searched and an exact model rule is persisted
- AND other endpoints are left unchanged for later research

#### Scenario: New model outside our connections does not trigger
- GIVEN a new `free`/`0-cost` model whose provider has no OmniRoute connection
- WHEN new-free-model detection runs
- THEN no recalc is triggered by that model

### Requirement: Search via OmniRoute gemini-grounded-search

The system SHALL obtain quota information through OmniRoute `POST /v1/search`
with provider `gemini-grounded-search`, using natural-language date-aware
queries, and SHALL treat the returned `answer.text` as the source. No separate
page fetch is performed. The query SHALL fit the live OmniRoute search request
schema, including the 500-character query limit, and SHALL omit internal provider
UUIDs when the model id is sufficient for a useful external search.

#### Scenario: Quota query
- GIVEN a provider needing a quota rule
- WHEN research runs
- THEN `/v1/search` is called with `gemini-grounded-search` and the `answer.text`
  summary is captured as an immutable snapshot
- AND the query is accepted by the live `/v1/search` schema

### Requirement: Instructor extraction

The system SHALL extract the quota claim from the snapshot text via Instructor
into a validated Pydantic structure; the LLM is not a source of truth beyond the
stored snapshot, and deterministic validation SHALL check amount > 0, metric and
window enums, presence of evidence, and unexpired dates.

#### Scenario: Invalid extracted claim
- GIVEN an extracted claim with a non-enum window
- WHEN deterministic validation runs
- THEN the claim is rejected

### Requirement: Summary-only activation with capped confidence

The system SHALL allow a quota rule to be activated directly from the summary
without an official page. Such a rule SHALL have confidence no greater than
`summary_confidence_cap`, `activated_by = summary`, and opportunistic capacity
class. A worsened quota SHALL move the endpoint to safe mode immediately; an
improved quota SHALL apply only after validation.

#### Scenario: Summary worsens quota
- GIVEN a new summary reports a lower limit than the active rule
- WHEN change detection runs
- THEN the endpoint is moved to safe mode immediately

### Requirement: Production quota research client

The system SHALL run quota research against the live OmniRoute search surface
(`POST /v1/search` with `gemini-grounded-search`) using configured credentials,
bounded retries, and immutable snapshot persistence of the returned
`answer.text`, unless a research result is explicitly injected. Structured
extraction SHALL run over the real search result. When the search source is
unavailable, the system SHALL fail conservatively and SHALL NOT produce a quota
rule from missing data.

#### Scenario: Live search performed
- GIVEN an endpoint needs a quota rule and no research result is injected
- WHEN quota research runs
- THEN `/v1/search` is called with `gemini-grounded-search` and configured auth
- AND the `answer.text` is persisted as an immutable snapshot before extraction

#### Scenario: Search unavailable
- GIVEN the search source is unavailable
- WHEN quota research runs
- THEN no quota rule is produced
- AND the endpoint remains without confirmed quota

### Requirement: Production quota stage uses the Instructor inspector

The production `quota-research` stage SHALL extract the quota claim through
`run_quota_inspector` over the shared runtime when it is available. The quota
inspector SHALL NOT set `site.model` to any hardcoded fabricated combo. It SHALL
leave the model unset so the shared runtime resolver selects a concrete provider
model at call time. In production that resolver is `select_llm_model`, which
returns the selected free provider model's `provider_model_id`. When no
resolver-selected provider model is available, the adapter SHALL fail closed as
`llm_model_unavailable` instead of calling a fabricated inspector combo. When
the inspector is unavailable or returns an unusable claim, the stage SHALL fail
open to the deterministic `extract_summary_claim` path. In both paths the
deterministic validator, `summary_confidence_cap`, and the worsen-quota rule
remain the source of truth; the inspector never raises a claim above what the
deterministic gate allows.

#### Scenario: Inspector path taken when runtime available
- **WHEN** the `quota-research` stage runs with the shared runtime available
- **THEN** the quota claim is extracted via `run_quota_inspector`
- **AND** the resulting rule is still capped by `summary_confidence_cap`

#### Scenario: Inspector uses resolver-selected provider model
- **GIVEN** the shared runtime resolver selects provider model `provider/model-a`
- **WHEN** `run_quota_inspector` calls the Instructor runtime
- **THEN** the outbound model id is `provider/model-a`
- **AND** no fabricated Inspector combo is used

#### Scenario: Resolver-less inspector fails closed
- **GIVEN** no resolver-selected provider model is available
- **WHEN** `run_quota_inspector` calls the Instructor runtime
- **THEN** the call fails closed as `llm_model_unavailable`
- **AND** no fabricated Inspector combo is used

#### Scenario: Fails open to deterministic extraction
- **WHEN** the inspector is unavailable or returns an unusable claim
- **THEN** the stage extracts the claim via `extract_summary_claim`
- **AND** the stage completes without failing the run

#### Scenario: Inspector cannot exceed the deterministic cap
- **WHEN** the inspector returns a confidence above `summary_confidence_cap`
- **THEN** the activated rule is clamped to the cap as opportunistic capacity

### Requirement: No-auth provider quota aliases

The system SHALL support explicit no-auth provider quota aliases when a no-auth
provider exposes the same model set and quota pool as an authenticated sibling
provider. An aliased no-auth provider SHALL inherit the sibling provider's model
expectations and quota rule and SHALL NOT be counted as independent capacity.

#### Scenario: Opencode shares opencode-zen quota
- GIVEN `opencode` is configured as a no-auth alias of `opencode-zen`
- WHEN quota research resolves quota for `opencode`
- THEN it uses the `opencode-zen` model and quota source
- AND `opencode` is marked as shared capacity with `opencode-zen`, not an
  independent quota pool

#### Scenario: Alias quota source missing
- GIVEN a no-auth provider has an authenticated sibling alias
- AND the sibling provider has no safe quota rule
- WHEN quota research resolves quota for the no-auth provider
- THEN the no-auth provider remains without usable quota
- AND no independent quota rule is inferred from the alias alone

### Requirement: Unknown no-auth provider calibration

The system SHALL mark no-auth providers with no reliable quota source as
calibration-required. A calibration-required provider SHALL NOT become usable
capacity until an operator places it first in a controlled combo, observes
OmniRoute token usage, and records the calibrated quota evidence. The recorded
evidence SHALL include observed token usage, inferred limit, reset window, and
hard-stop status before quota research can activate the rule.

#### Scenario: Unknown no-auth quota requires observation
- GIVEN a no-auth provider has no quota from registry, live quota, alias, or
  search
- WHEN quota research resolves the provider
- THEN the provider is marked calibration-required
- AND it is not treated as usable capacity

#### Scenario: Calibrated usage promotes quota
- GIVEN a calibration-required no-auth provider was placed first in a controlled
  combo
- AND OmniRoute token usage shows the limit, reset window, and hard-stop status
- WHEN the operator records the calibration evidence
- THEN quota research can activate the provider quota rule from that evidence

#### Scenario: Incomplete calibration stays inactive
- GIVEN a calibration-required no-auth provider has observed token usage
- AND the observation does not establish limit, reset window, or hard-stop status
- WHEN quota research evaluates the evidence
- THEN the provider remains calibration-required
- AND no usable quota is activated

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

### Requirement: Sub-day request rates are quota capacity rules

The system SHALL treat a sub-day request rate (`requests` with window `minute` or
`hour`) as usable request capacity, because routing demand is request-count
based even when token volume is unrestricted. Such a rule SHALL remain marked
with its original sub-day window; normalization may convert it to a conservative
daily request ceiling for ranking. This routing SHALL apply identically to
deterministic-summary claims and to Instructor-inspector claims; otherwise an
inspector-returned `metric` SHALL be carried through unchanged.

#### Scenario: Requests-per-minute only activates
- GIVEN a summary expressing only N requests per minute
- WHEN extraction runs
- THEN a `requests/minute` capacity rule is activated

#### Scenario: Inspector token claim carried through
- GIVEN the Instructor inspector returns a claim with metric `tokens`
- WHEN the claim is activated
- THEN the metric is carried through unchanged and capped by `summary_confidence_cap`

#### Scenario: Inspector sub-day request claim carried through
- GIVEN the Instructor inspector returns a `requests` claim with a `minute` window
- WHEN the claim is processed
- THEN the `requests/minute` capacity rule is activated

### Requirement: Per-endpoint research failures degrade, not abort

The production `quota-research` stage SHALL isolate per-endpoint failures: an
error researching one endpoint SHALL be recorded and that endpoint skipped, and
the stage SHALL continue researching the remaining endpoints rather than
returning on the first error. When one or more endpoints failed, the stage SHALL
report `partial_stale` rather than `external_dependency_failed`, so the run
continues with the endpoints that did succeed.

#### Scenario: One endpoint error does not stop research for the rest
- GIVEN three endpoints need quota research and the second one errors
- WHEN the `quota-research` stage runs
- THEN the first and third endpoints are still researched and persisted
- AND the second endpoint is recorded as failed and skipped

#### Scenario: Per-endpoint failures mark the run partial
- GIVEN at least one endpoint failed during quota research while others succeeded
- WHEN the stage finishes
- THEN it returns `partial_stale`
- AND the run is not failed as `external_dependency_failed`

### Requirement: Inspector resolves a reported range using the prior limit

The Instructor inspector SHALL collapse a quota reported as a range `[low, high]`
into a single `amount` within that range, anchored to the previously trusted
limit. The system SHALL thread `previous_limit` into the inspector path so it is
available to the inspector prompt. The inspector SHALL return the value in
`[low, high]` closest to `previous_limit` (the prior limit clamped into the
range); when `previous_limit` is unknown, the inspector SHALL return the
conservative lower bound `low`. The deterministic validator,
`summary_confidence_cap`, and the worsen-quota safe-mode rule remain the source of
truth; range resolution only selects a value within the evidence bounds and never
raises a claim above what the gate allows.

#### Scenario: Prior limit inside the range is kept
- GIVEN a snapshot range of `[low, high]` and a `previous_limit` within it
- WHEN the inspector resolves the claim
- THEN the resolved amount equals `previous_limit`

#### Scenario: Range below the prior limit resolves to its upper bound
- GIVEN a snapshot range entirely below `previous_limit` (a downgrade)
- WHEN the inspector resolves the claim
- THEN the resolved amount equals the range's upper bound `high`

#### Scenario: Range above the prior limit resolves to its lower bound
- GIVEN a snapshot range entirely above `previous_limit` (an unverified upgrade)
- WHEN the inspector resolves the claim
- THEN the resolved amount equals the range's lower bound `low`

#### Scenario: No prior limit resolves conservatively
- GIVEN a snapshot range of `[low, high]` and no `previous_limit`
- WHEN the inspector resolves the claim
- THEN the resolved amount equals the conservative lower bound `low`

#### Scenario: Prior limit reaches the inspector prompt
- GIVEN quota research runs with a `previous_limit` and an available inspector
- WHEN extraction is delegated to the inspector
- THEN the configured prompt file's `{{previous_limit}}` placeholder resolves to
  that value in the assembled prompt
