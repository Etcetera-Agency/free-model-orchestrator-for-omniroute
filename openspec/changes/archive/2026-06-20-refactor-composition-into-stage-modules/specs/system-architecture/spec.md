## ADDED Requirements

### Requirement: Composition root stays within a single-responsibility boundary

The production composition root SHALL wire stages, the CLI dispatcher, and the
AA-index handlers from focused per-domain modules rather than defining them all
in one module. No single composition module SHALL own stage adapters across
unrelated domains together with the CLI dispatcher and the AA-index handlers.
Refactoring the composition layout SHALL NOT change any stage behavior, exit
code, persisted shape, or CLI surface; the existing test suite SHALL pass
unchanged as the behavior-preservation oracle.

#### Scenario: Stage domains live in separate modules
- **WHEN** the composition layer is inspected
- **THEN** stage adapters are grouped by domain in dedicated modules, the CLI
  dispatcher and AA-index handlers are separate, and the composition root only
  wires them together

#### Scenario: Refactor preserves behavior
- **WHEN** the composition root is decomposed into per-domain modules
- **THEN** the full existing pytest suite passes unchanged
- **AND** no stage behavior, exit code, persisted shape, or CLI command changes
