# system-architecture Specification

## Purpose
Define the reduced publisher-only architecture and package boundaries.

## Requirements

### Requirement: Runtime architecture is publisher-only
The composition root SHALL wire current publisher stages through domain modules
and SHALL NOT retain retired discovery/matching/probing/apply modules.

#### Scenario: Stage domains live in separate modules
- **WHEN** composition is inspected
- **THEN** stage bodies live outside the root module.

#### Scenario: Refactor preserves behavior
- **WHEN** the stage package is imported
- **THEN** current adapters remain callable.

#### Scenario: No legacy delegation module remains
- **WHEN** stage modules are scanned
- **THEN** no `_legacy` module remains.

#### Scenario: Stage package re-exports preserve composition wiring
- **WHEN** composition imports stage package exports
- **THEN** current stage adapters are available.

#### Scenario: Shared stage helpers live in one helpers module
- **WHEN** shared stage helpers are inspected
- **THEN** they come from `composition_stages._helpers`.

#### Scenario: Row access helpers are defined once in the persistence base
- **WHEN** row helper definitions are scanned
- **THEN** they only exist in `persistence/_base.py`.

#### Scenario: Persistence public API stays import-stable
- **WHEN** the persistence package is imported
- **THEN** current repository classes are re-exported.

#### Scenario: Persistence layer is split into per-aggregate modules
- **WHEN** the persistence package is inspected
- **THEN** current aggregate modules are separate files.

#### Scenario: Re-run with unchanged inputs
- **WHEN** stable hashes compare equivalent payloads
- **THEN** unchanged inputs produce the same hash.

#### Scenario: Test suite runs from both pytest entry points
- **WHEN** pytest is run by package or module entrypoint
- **THEN** the shared import path is configured.

#### Scenario: Intraday failure not rebuilt
- **WHEN** OmniRoute observes intraday model failures
- **THEN** OmniRoute handles routing/fallback without FMO rebuilding combos.
