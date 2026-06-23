## MODIFIED Requirements

### Requirement: Shared helpers have a single canonical definition

Duplicated cross-module helpers SHALL each have exactly one canonical definition,
with call sites importing it rather than reimplementing: the repository row
helpers live in `persistence/_base`; the timestamp (`utcnow`), slug, and hashing
helpers live in one shared module each; and the quota-math helpers live next to
the quota normalization/manager modules. Stage cluster modules SHALL import the
canonical helper name directly from its module; the `composition_stages._helpers`
module SHALL NOT carry a per-package re-export alias layer (e.g. `_canonical_slug
= canonical_slug`) for those helpers. Consolidation SHALL NOT change any
behavior — it removes duplicate definitions and redundant aliases only; the
existing test suite SHALL pass unchanged as the behavior-preservation oracle.

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

#### Scenario: Stage helpers carry no re-export alias layer
- **WHEN** the `composition_stages._helpers` module is inspected
- **THEN** it defines only the genuine cross-cluster stage helpers and no
  underscore re-export alias (`_canonical_slug`, `_hash_parts`, `_quota_metric`,
  `_quota_limit`, `_remaining_amount`) for the centralized helpers
- **AND** the cluster modules import those helpers directly from
  `fmo.idempotency` / `fmo.quota_normalize`
