## MODIFIED Requirements

### Requirement: Probing, telemetry, inventory, and role stages are dedicated modules

The middle-of-pipeline stages SHALL be **defined** in dedicated per-cluster
modules under the `fmo.composition_stages` package — probing, telemetry sync,
Hermes inventory, role lifecycle, and role scoring. The role-scoring helper
cluster (health/stability/latency components, quality-band seeding, AA-metric and
health lookups) SHALL be defined with the role stage rather than in the package
root. The module that fronts a middle-of-pipeline stage SHALL contain the stage's
implementation rather than a delegation to another module (in particular not to
`_legacy`). Draining these clusters SHALL NOT change any stage behavior, scoring
output, or persisted shape; the existing test suite SHALL pass unchanged as the
behavior-preservation oracle.

#### Scenario: Probing, telemetry, inventory, and role stages live in dedicated modules
- **WHEN** the composition stages package is inspected
- **THEN** the probing, telemetry-sync, Hermes-inventory, role-lifecycle, and
  role-scoring stages live in separate cluster modules under
  `fmo.composition_stages`
- **AND** all stages still resolve unchanged through the production adapter table

#### Scenario: Middle-of-pipeline stages are defined in their own modules
- **WHEN** a middle-of-pipeline stage entrypoint is inspected with
  `inspect.getmodule`
- **THEN** it resolves to its cluster module (`probing`, `telemetry`, `inventory`,
  or `roles`)
- **AND** it does not resolve to `fmo.composition_stages._legacy`

#### Scenario: Role scoring helpers move with the role stage
- **WHEN** the role module is inspected
- **THEN** the health/stability/latency components, quality-band seeding, and
  AA/health lookup helpers are defined alongside the role stage
- **AND** the full existing pytest suite passes unchanged
