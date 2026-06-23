## MODIFIED Requirements

### Requirement: Discovery, quota, and access stages are dedicated modules

The front-of-pipeline stages SHALL be **defined** in dedicated per-cluster
modules under the `fmo.composition_stages` package — metadata, free-candidate and
account discovery, model matching, quota research/sync, and access classification
— each owning its own private helpers, rather than in a single stage module. The
module that fronts a front-of-pipeline stage SHALL contain the stage's
implementation rather than a delegation to another module (in particular not to
`_legacy`). Draining these clusters SHALL NOT change any stage behavior, persisted
shape, or the production stage-adapter wiring; the existing test suite SHALL pass
unchanged as the behavior-preservation oracle.

#### Scenario: Discovery, quota, and access stages live in dedicated modules
- **WHEN** the composition stages package is inspected
- **THEN** the discovery, quota-research/sync, and access-classification stages
  live in separate cluster modules under `fmo.composition_stages`
- **AND** no extracted module defines a stage belonging to a different cluster

#### Scenario: Front-of-pipeline stages are defined in their own modules
- **WHEN** a front-of-pipeline stage entrypoint is inspected with
  `inspect.getmodule`
- **THEN** it resolves to its cluster module (`discovery`, `quota`, or `access`)
- **AND** it does not resolve to `fmo.composition_stages._legacy`

#### Scenario: Stage package re-exports preserve composition wiring
- **WHEN** `composition.py` and `_production_stage_adapters()` resolve the moved
  stages
- **THEN** every stage and shared name resolves unchanged through the package
  re-export
- **AND** the full existing pytest suite passes unchanged
