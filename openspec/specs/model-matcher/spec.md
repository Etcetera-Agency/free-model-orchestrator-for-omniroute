# model-matcher Specification

## Purpose
TBD - created by archiving change add-discovery. Update Purpose after archive.
## Requirements
### Requirement: Ordered canonical matching

The system SHALL resolve a provider model id to a canonical model in order:
manual alias; previous confirmed match; exact models.dev provider model id; exact
canonical slug; lab+family+version; constrained fuzzy candidate; LLM suggestion;
unmatched. All attempts SHALL be stored in `model_match_candidates`;
`provider_endpoints.canonical_model_id` changes only on an accepted match.

#### Scenario: Exact slug match
- GIVEN a normalized id equal to a canonical slug
- WHEN matching runs
- THEN that canonical model is matched at exact-slug confidence

### Requirement: Forbidden automatic merges

The system SHALL NOT automatically merge base vs instruct, normal vs thinking,
low vs high reasoning, preview vs stable, different dated snapshots, or mini vs
full.

#### Scenario: Base vs instruct
- GIVEN a provider exposes both base and instruct variants
- WHEN matching runs
- THEN they are not auto-merged into one canonical model

### Requirement: Confidence gate

The system SHALL assign match confidence (1.00 manual, 0.98 exact provider
catalog, 0.95 exact slug, 0.85 normalized structured, below 0.85
review_required) and auto-use a match in scoring only at confidence ≥ 0.90.

#### Scenario: Low-confidence match
- GIVEN a match at confidence 0.85
- WHEN scoring requests an endpoint's canonical model
- THEN the match is flagged review_required and not auto-used

### Requirement: Provider capabilities override canonical

The system SHALL keep provider-specific capabilities and context/output limits on
the endpoint and give them precedence over canonical metadata; the smaller
confirmed context value wins on conflict. A provider context-limit change SHALL
invalidate role scores and allocation.

#### Scenario: Smaller provider context
- GIVEN canonical context 128K and provider context 32K for an endpoint
- WHEN effective context is computed
- THEN the endpoint's effective context is 32K

