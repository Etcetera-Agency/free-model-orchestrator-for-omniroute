## ADDED Requirements

### Requirement: Stage bodies are defined in their domain modules

Each pipeline stage and its private helpers SHALL be **defined** in the domain
module under `fmo.composition_stages` that owns its cluster — not re-exported
there from a shared catch-all module. No `_legacy` (or otherwise named single
delegation/monolith) module SHALL remain under `fmo.composition_stages`; besides
the `__init__` re-export shim, the package SHALL contain only the cluster stage
modules, the cross-cluster `_helpers` module, and the shared `_base` module (the
`Stage*` dataclasses and the base `_production_stage_adapters` builder). Draining
the bodies SHALL NOT change any stage behavior, apply-safety decision, persisted
shape, idempotency key, or exit code; the existing test suite SHALL pass unchanged
as the behavior-preservation oracle, and the package's public re-export surface
SHALL stay identical.

#### Scenario: Each stage resolves to its own domain module
- **WHEN** a stage entrypoint exposed by the `fmo.composition_stages` package is
  inspected with `inspect.getmodule`
- **THEN** it resolves to the cluster module that owns it (e.g. `_apply_stage` to
  `fmo.composition_stages.apply`)
- **AND** it does not resolve to a `fmo.composition_stages._legacy` module

#### Scenario: No legacy delegation module remains
- **WHEN** the `fmo.composition_stages` package directory is inspected
- **THEN** there is no `_legacy` module and no package module imports `_legacy`
- **AND** the full existing pytest suite passes unchanged

## MODIFIED Requirements

### Requirement: Allocation, apply, rollback, and audit stages are dedicated modules

The back-of-pipeline stages SHALL be **defined** in dedicated per-cluster modules
under the `fmo.composition_stages` package — demand forecast, allocation, diff,
apply, rollback, and audit — and the cross-cluster shared helpers (effect/result,
slug/hash, quota-math, adapter helpers) SHALL be defined once in a single helpers
module imported by the domain modules. The module that fronts a back-of-pipeline
stage SHALL contain the stage's implementation rather than a delegation to another
module. After the drain the package SHALL contain only the re-export shim, the
cluster stage modules, the `_helpers` module, and the `_base` module holding the
stage dataclasses and base adapter builder; no `_legacy` delegation module SHALL
remain. The split SHALL NOT change any stage behavior, apply-safety decision,
persisted shape, or exit code; the existing test suite SHALL pass unchanged as the
behavior-preservation oracle.

#### Scenario: Allocation, apply, rollback, and audit stages live in dedicated modules
- **WHEN** the composition stages package is inspected
- **THEN** the allocation, apply, rollback, and audit stages are defined in
  separate cluster modules under `fmo.composition_stages`
- **AND** no `_legacy` or other monolithic stage module remains alongside the
  package

#### Scenario: Shared stage helpers live in one helpers module
- **WHEN** a domain stage module uses a cross-cluster helper
- **THEN** that helper is imported from the single shared helpers module rather
  than redefined per cluster
- **AND** the full existing pytest suite passes unchanged
