## ADDED Requirements

### Requirement: Allocation, apply, rollback, and audit stages are dedicated modules

The back-of-pipeline stages SHALL live in dedicated per-cluster modules under the
`fmo.composition_stages` package — demand forecast, allocation, diff, apply,
rollback, and audit — and the cross-cluster shared helpers (effect/result,
slug/hash, quota-math, adapter helpers) SHALL be defined once in a single helpers
module imported by the domain modules. After the split the
package root SHALL contain only the re-export shim and the stage dataclasses; no
monolithic stage module SHALL remain. The split SHALL NOT change any stage
behavior, apply-safety decision, persisted shape, or exit code; the existing test
suite SHALL pass unchanged as the behavior-preservation oracle.

#### Scenario: Allocation, apply, rollback, and audit stages live in dedicated modules
- **WHEN** the composition stages package is inspected
- **THEN** the allocation, apply, rollback, and audit stages live in separate
  cluster modules under `fmo.composition_stages`
- **AND** no monolithic `composition_stages` module remains alongside the package

#### Scenario: Shared stage helpers live in one helpers module
- **WHEN** a domain stage module uses a cross-cluster helper
- **THEN** that helper is imported from the single shared helpers module rather
  than redefined per cluster
- **AND** the full existing pytest suite passes unchanged
