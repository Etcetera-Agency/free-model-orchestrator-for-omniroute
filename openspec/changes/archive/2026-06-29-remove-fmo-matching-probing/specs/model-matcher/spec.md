# model-matcher Specification

## REMOVED Requirements

### Requirement: Ordered canonical matching
**Reason**: Model matching and score normalization move to OmniRoute's `model_intelligence`.
**Migration**: OmniRoute resolves a model's score by source precedence (`user_override > arena_elo > models_dev_tier`).

### Requirement: Variant-specific canonical, never merged
**Reason**: Variant handling belongs to OmniRoute's model catalog + intelligence ingestion.
**Migration**: OmniRoute catalog/sync owns variant identity.

### Requirement: Confidence gate
**Reason**: Confidence handling moves with model intelligence to OmniRoute.
**Migration**: OmniRoute uses `model_intelligence.confidence` when resolving the band.

### Requirement: Provider capabilities override canonical
**Reason**: Capability resolution moves to OmniRoute (models.dev + compat overrides).
**Migration**: OmniRoute enriches candidates with capabilities during inventory build.
