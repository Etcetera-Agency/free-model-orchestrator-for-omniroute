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

The reviewer prompt SHALL be assembled from a deterministic, redacted context
bundle that includes the current live combo, deterministic target combo,
minimal deterministic diff, role requirements, demand forecast, allocation
constraint report, bounded candidate registry with scoring/capability/quota
facts, quota attribution summary, provider/account diversity summary,
deterministic validation report, and apply precondition summary. The reviewer
SHALL load its external prompt file through the shared Instructor runtime. If the
context would exceed the site prompt limit, deterministic code SHALL summarize
candidate details while preserving every required top-level section.

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

#### Scenario: Reviewer receives deterministic combo context
- **WHEN** the production diff stage invokes the reviewer
- **THEN** the prompt context includes `role_id`, `current_combo`,
  `target_combo`, and `deterministic_diff`

#### Scenario: Reviewer receives planning and safety facts
- **WHEN** the production diff stage invokes the reviewer
- **THEN** the prompt context includes role requirements, demand forecast,
  allocation constraint report, candidate registry, quota summary, diversity
  summary, validation report, and apply precondition summary

#### Scenario: Reviewer uses external prompt file
- **WHEN** an operator edits `reference/prompts/smart-combo-reviewer.md`
- **THEN** the next reviewer call renders that prompt file through the shared
  Instructor runtime

#### Scenario: Reviewer prompt remains bounded and complete
- **GIVEN** the candidate registry is larger than the reviewer prompt budget
- **WHEN** the reviewer context is assembled
- **THEN** candidate details are summarized deterministically
- **AND** every required top-level context section remains present

#### Scenario: Reviewer prompt redacts secrets
- **GIVEN** reviewer source data contains secret-like keys or values
- **WHEN** the reviewer prompt is rendered
- **THEN** secrets are omitted or redacted before the LLM transport receives the
  prompt

