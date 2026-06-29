# quota-research Specification

## REMOVED Requirements

### Requirement: Primary quota source where OmniRoute is silent
**Reason**: Quota research moves to OmniRoute, which owns live quota and the request path.
**Migration**: OmniRoute resolves quota by source precedence (live → static → search → calibration).

### Requirement: Search via OmniRoute gemini-grounded-search
**Reason**: Search-research becomes OmniRoute quota tier 3.
**Migration**: OmniRoute runs the search claim only when no live or static number exists.

### Requirement: Instructor extraction
**Reason**: Quota LLM extraction relocates with quota research.
**Migration**: OmniRoute owns the extraction in its quota layer.

### Requirement: Summary-only activation with capped confidence
**Reason**: Relocated with quota research.
**Migration**: Handled inside OmniRoute quota research.

### Requirement: Production quota research client
**Reason**: FMO no longer runs quota research.
**Migration**: OmniRoute owns the client.

### Requirement: Production quota stage uses the Instructor inspector
**Reason**: The quota stage is removed from the FMO pipeline.
**Migration**: N/A — quota stage retired.

### Requirement: No-auth provider quota aliases
**Reason**: No-auth quota aliasing relocates with quota research.
**Migration**: OmniRoute owns no-auth alias handling.

### Requirement: Unknown no-auth provider calibration
**Reason**: The place-first calibration canary moves to OmniRoute (quota tier 4).
**Migration**: OmniRoute seats a no-number candidate first and learns its ceiling.

### Requirement: Summary extraction captures the present quota axis
**Reason**: Relocated with quota research.
**Migration**: Handled inside OmniRoute quota research.

### Requirement: Sub-day request rates are quota capacity rules
**Reason**: Rate-window capacity is part of OmniRoute's request-equivalents comparator.
**Migration**: OmniRoute converts rate windows to request-equivalents/day.

### Requirement: Per-endpoint research failures degrade, not abort
**Reason**: Removed with the FMO quota stage.
**Migration**: OmniRoute handles per-candidate quota failures during materialization.

### Requirement: Inspector resolves a reported range using the prior limit
**Reason**: Relocated with quota research.
**Migration**: OmniRoute owns range resolution in its quota layer.
