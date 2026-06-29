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

#### Scenario: Provider punctuation and tuning aliases
- GIVEN Artificial Analysis canonical slug `minimax-m2-7`
- AND provider model id `nvidia/minimaxai/minimax-m2.7`
- WHEN matching runs
- THEN the endpoint is matched to canonical slug `minimax-m2-7`
- AND it is auto-used at exact-slug confidence
- GIVEN Artificial Analysis canonical slug `gemma-3n-e2b`
- AND provider model id `nvidia/google/gemma-3n-e2b-it`
- WHEN matching runs
- THEN the endpoint is matched to canonical slug `gemma-3n-e2b`
- AND it is auto-used at exact-slug confidence
- AND if a stale provider-specific canonical slug such as `gemma-3n-e2b-it`
  already exists without AA metrics, the AA-backed canonical slug still wins
- AND the endpoint binding is overwritten to the AA-backed canonical row without
  retaining an unreferenced duplicate canonical alias

### Requirement: Variant-specific canonical, never merged

The system SHALL NOT automatically merge base vs instruct, normal vs thinking,
low vs high reasoning, preview vs stable, different dated snapshots, or mini vs
full. Because Artificial Analysis scores these variants as distinct models, the
system SHALL achieve non-merge by binding each provider model id to a canonical
slug that preserves its variant suffix: a known canonical or AA-backed slug wins,
otherwise a new variant-specific canonical is created from the full normalized
slug. The system SHALL NOT strip variant suffixes (`-thinking`, `-reasoning`,
`-instruct`, `-base`, `-mini`, dated snapshots) when forming a canonical slug.

#### Scenario: Base vs instruct
- GIVEN a provider exposes both base and instruct variants
- AND neither variant slug exists as a canonical model yet
- WHEN matching runs
- THEN each variant is registered as its own canonical model
- AND they are never collapsed into one canonical model

#### Scenario: Variant-specific canonical
- GIVEN a provider model id `gpt-4.1-preview`
- AND only the base canonical slug `gpt-4.1` exists
- WHEN matching runs
- THEN a new canonical slug `gpt-4.1-preview` is created and auto-used
- AND the model is not parked in review and not merged onto `gpt-4.1`

### Requirement: Confidence gate

The system SHALL assign match confidence (1.00 manual, 0.97 AA-backed exact slug,
0.95 exact canonical slug, 0.90 new variant-specific canonical, below 0.90
review_required) and auto-use a match in scoring only at confidence ≥ 0.90.

#### Scenario: Auto-used match
- GIVEN a match at confidence ≥ 0.90
- WHEN scoring requests an endpoint's canonical model
- THEN the match is auto-used and not flagged review_required

### Requirement: Provider capabilities override canonical

The system SHALL keep provider-specific capabilities and context/output limits on
the endpoint and give them precedence over canonical metadata; the smaller
confirmed context value wins on conflict. A provider context-limit change SHALL
invalidate role scores and allocation.

#### Scenario: Smaller provider context
- GIVEN canonical context 128K and provider context 32K for an endpoint
- WHEN effective context is computed
- THEN the endpoint's effective context is 32K
