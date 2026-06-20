## ADDED Requirements

### Requirement: Advisory reviewer runs in the production diff path

The production pipeline SHALL invoke `run_combo_review` as an advisory pass over
the computed combo diff using the shared runtime. The reviewer is fail-open and
advisory only: its structured output SHALL be persisted for operator visibility,
but the applied diff SHALL be exactly the deterministic diff regardless of
whether the reviewer succeeds, fails, or is disabled.

#### Scenario: Reviewer output is recorded
- **WHEN** the diff stage runs with the advisory reviewer enabled
- **THEN** the reviewer's structured result is persisted alongside the diff

#### Scenario: Applied diff is independent of the reviewer
- **WHEN** the same run is executed with the reviewer succeeding and with the
  reviewer unavailable
- **THEN** the applied diff is byte-identical in both runs
- **AND** a reviewer result that alters the applied diff fails the suite

#### Scenario: Reviewer disabled by trigger
- **WHEN** the advisory trigger is disabled
- **THEN** no reviewer call is made and the deterministic diff is applied
