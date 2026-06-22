# data-model Specification

## ADDED Requirements

### Requirement: Role carries a quality band upper bound

The `roles` table SHALL carry `maximum_quality_metric` and
`maximum_quality_value` beside the existing `minimum_quality_metric` /
`minimum_quality_value`, with a metric check matching the minimum's
(`intelligence_index | coding_index | agentic_index`). Together they express the
role's quality band `[min, max]`. The columns are nullable; a NULL maximum means
no upper bound (min-only behavior).

#### Scenario: Role carries a maximum quality bound
- GIVEN a fresh schema install (or applied migration)
- WHEN a role is written with a band
- THEN `maximum_quality_metric` / `maximum_quality_value` persist and round-trip
- AND a role written without an upper bound stores NULL for the maximum
