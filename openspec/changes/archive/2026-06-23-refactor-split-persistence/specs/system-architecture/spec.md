## ADDED Requirements

### Requirement: Persistence layer is a package of per-aggregate modules

The persistence layer SHALL be a `fmo.persistence` package with one module per
domain aggregate over a shared `_base` module that owns the `Database`,
`Repository`, and module-private row helpers (`_one`, `_optional`, `_many`,
`_jsonb`, content/hash helpers). No single aggregate module SHALL own the
repositories of unrelated aggregates, and table SQL SHALL remain confined to its
aggregate's repository module. Splitting the layer SHALL NOT change any persisted
shape, query, or repository behavior; the existing test suite SHALL pass
unchanged as the behavior-preservation oracle.

#### Scenario: Persistence layer is split into per-aggregate modules
- **WHEN** the persistence layer is inspected
- **THEN** `fmo.persistence` is a package with one module per aggregate and a
  shared `_base` module owning `Database`, `Repository`, and the row helpers
- **AND** no aggregate module defines repositories for an unrelated aggregate

#### Scenario: Persistence public API stays import-stable
- **WHEN** existing call sites import `Database`, `Repository`, or any
  `*Repository` from `fmo.persistence`
- **THEN** every previously public name resolves unchanged through the package
  `__init__` re-export
- **AND** the full existing pytest suite passes unchanged
