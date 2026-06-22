# demand-forecast Specification

## ADDED Requirements

### Requirement: Shared combo demand sums across slots

The system SHALL sum the `calls_per_run` of every Hermes slot that routes to the
same OmniRoute combo — main or auxiliary, in the same or different profiles —
into that combo's aggregated demand, so a shared combo's forecast reflects total
load rather than any single referencing slot.

#### Scenario: Shared combo sums demand across slots
- GIVEN two profiles whose auxiliary `vision` slots both point at combo `C`
- WHEN demand is aggregated
- THEN combo `C`'s demand is the sum of both slots' `calls_per_run`
- AND a third profile routing its main combo to `C` adds its load to the same sum
