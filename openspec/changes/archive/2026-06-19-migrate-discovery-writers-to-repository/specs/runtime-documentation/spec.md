## MODIFIED Requirements

### Requirement: Runtime docs match shipped behavior

The README, repo-level `completion.review`, and `openspec/TODO.md` SHALL reflect
the shipped runtime behavior, archived/active OpenSpec state, and current status
of the executable-spec pending allowlist. They SHALL NOT claim there is no
deferred work while active changes or TODO entries still identify deferred or
follow-up work.

#### Scenario: Runtime docs reflect validation and pending coverage
- **WHEN** runtime docs describe the current implementation
- **THEN** they name the production composition behavior actually shipped
- **AND** they state the current status of the pending allowlist
- **AND** uncovered scenarios are represented either by active OpenSpec changes
  or by an empty pending allowlist

#### Scenario: TODO does not contradict active work
- **WHEN** `openspec/TODO.md` lists active or deferred follow-up work
- **THEN** it does not also claim that no deferred work exists for that area
