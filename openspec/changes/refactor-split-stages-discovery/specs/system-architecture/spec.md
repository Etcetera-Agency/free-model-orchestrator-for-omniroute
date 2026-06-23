## ADDED Requirements

### Requirement: Discovery, quota, and access stages are dedicated modules

The front-of-pipeline stages SHALL live in dedicated per-cluster modules under
the `fmo.composition_stages` package — metadata, free-candidate and account
discovery, model matching, quota research/sync, and access classification — each
owning its own private helpers, rather than in a single stage module. Extracting
these clusters SHALL NOT change any stage behavior, persisted shape, or the
production stage-adapter wiring; the existing test suite SHALL pass unchanged as
the behavior-preservation oracle.

#### Scenario: Discovery, quota, and access stages live in dedicated modules
- **WHEN** the composition stages package is inspected
- **THEN** the discovery, quota-research/sync, and access-classification stages
  live in separate cluster modules under `fmo.composition_stages`
- **AND** no extracted module defines a stage belonging to a different cluster

#### Scenario: Stage package re-exports preserve composition wiring
- **WHEN** `composition.py` and `_production_stage_adapters()` resolve the moved
  stages
- **THEN** every stage and shared name resolves unchanged through the package
  re-export
- **AND** the full existing pytest suite passes unchanged
