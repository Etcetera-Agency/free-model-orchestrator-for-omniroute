# smart-combo-reviewer Specification

## Purpose
TBD - created by archiving change add-advisory-llm. Update Purpose after archive.
## Requirements
### Requirement: Single advisory structured call

The system SHALL make at most one advisory structured LLM call per review. If
triggering is disabled, review SHALL return skipped. If the Instructor call
throws, review SHALL return failed without blocking deterministic allocation.

#### Scenario: Trigger disabled
- GIVEN smart review trigger is false
- WHEN review is requested
- THEN status is `skipped_trigger`

#### Scenario: Instructor call fails
- GIVEN the Instructor call raises an exception
- WHEN review is requested
- THEN status is `failed`

### Requirement: Independent diff validation, no repair loop

The system SHALL validate each proposed diff independently and SHALL NOT ask the
LLM to repair invalid output. Unknown endpoint adds, removals below minimum combo
size, remove/move of absent endpoint, and duplicate adds SHALL be handled
deterministically. Duplicate add SHALL be idempotent.

#### Scenario: Unknown endpoint add
- GIVEN a diff adds an endpoint not known to the plan
- WHEN diffs are applied
- THEN that diff is rejected as `unknown_endpoint`

#### Scenario: Remove below minimum combo size
- GIVEN a diff removes an endpoint and would shrink combo below minimum size
- WHEN diffs are applied
- THEN that diff is rejected for minimum combo size

#### Scenario: Missing endpoint remove or move
- GIVEN a diff removes or moves an endpoint absent from the combo
- WHEN diffs are applied
- THEN that diff is rejected as `endpoint_missing`

#### Scenario: Duplicate add
- GIVEN a diff adds an endpoint already present in the combo
- WHEN diffs are applied
- THEN the combo is unchanged and no duplicate is created

### Requirement: Advisory only — never blocks the deterministic plan

The system SHALL apply the deterministic combo when the reviewer model is
unavailable (`skipped_no_model`), the structured output fails (`failed`), or all
diffs are rejected (`no_valid_diffs`). Review SHALL run only on configured
triggers, and SHALL never call `/api/combos/test`.

#### Scenario: Reviewer model unavailable
- GIVEN no eligible reviewer model is available
- WHEN the review step runs
- THEN the deterministic combo is applied unchanged with status `skipped_no_model`

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

