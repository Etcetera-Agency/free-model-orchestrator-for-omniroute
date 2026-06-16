# quota-research Specification

## ADDED Requirements

### Requirement: Primary quota source where OmniRoute is silent

The system SHALL use quota research as the primary source of quota for any
endpoint not covered by an official quota API or by OmniRoute (the free registry
and rate-limits cover only a subset of providers). It SHALL NOT re-search daily
an endpoint whose free access is already confirmed and whose rule is not stale.

#### Scenario: Endpoint absent from OmniRoute registry
- GIVEN an endpoint with no confirmed quota from any official API or OmniRoute
- WHEN the daily batch reaches quota research
- THEN that endpoint is researched to obtain a rule

### Requirement: Search via OmniRoute gemini-grounded-search

The system SHALL obtain quota information through OmniRoute `POST /v1/search`
with provider `gemini-grounded-search`, using natural-language date-aware
queries, and SHALL treat the returned `answer.text` as the source. No separate
page fetch is performed.

#### Scenario: Quota query
- GIVEN a provider needing a quota rule
- WHEN research runs
- THEN `/v1/search` is called with `gemini-grounded-search` and the `answer.text`
  summary is captured as an immutable snapshot

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
