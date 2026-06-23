## ADDED Requirements

### Requirement: Shared helpers have a single canonical definition

Duplicated cross-module helpers SHALL each have exactly one canonical definition,
with call sites importing it rather than reimplementing: the repository row
helpers live in `persistence/_base`; the timestamp (`utcnow`), slug, and hashing
helpers live in one shared module each; and the quota-math helpers live next to
the quota normalization/manager modules. Consolidation SHALL NOT change any
behavior — it removes duplicate definitions only; the existing test suite SHALL
pass unchanged as the behavior-preservation oracle.

#### Scenario: Row access helpers are defined once in the persistence base
- **WHEN** a module needs a repository row helper (`_one`, `_optional`, `_many`,
  `_jsonb`, `_content_hash`)
- **THEN** it imports the single definition from `persistence/_base`
- **AND** no stage module reimplements the helper

#### Scenario: Timestamp and hashing helpers are centralized
- **WHEN** a module needs the UTC-now, canonical-slug, hash, idempotency-key, or
  quota-math helper
- **THEN** it imports the one canonical definition for that helper
- **AND** the full existing pytest suite passes unchanged
