# smart-combo-reviewer Specification

## ADDED Requirements

### Requirement: Single advisory structured call

The system SHALL run at most one Instructor structured call that returns a
`ComboReview` of already-built combos, proposing only `add`, `remove` or `move`
operations. The reviewer SHALL NOT change routing strategy, endpoint weights,
quota, quota attribution, free/paid classification, quality gate, capabilities,
context limits, demand, the historical reserve, bootstrap profiles, role
definitions, credentials or provider configuration, and SHALL NOT invent an
endpoint absent from the candidate registry.

#### Scenario: Reviewer proposes a weight change
- GIVEN a reviewer response attempting to set endpoint weights
- WHEN the diff is processed
- THEN it is rejected because weights are not a permitted operation

### Requirement: Independent diff validation, no repair loop

The system SHALL apply diffs to a copy one at a time, run deterministic validation
after each, and ignore only the invalid diff (recording its rejection reason)
while continuing with the others. The reviewer SHALL NOT get a second repair loop.

#### Scenario: One invalid diff among several
- GIVEN three proposed diffs where one fails validation
- WHEN diffs are applied
- THEN the valid two are kept and the invalid one is logged and skipped

### Requirement: Advisory only — never blocks the deterministic plan

The system SHALL apply the deterministic combo when the reviewer model is
unavailable (`skipped_no_model`), the structured output fails (`failed`), or all
diffs are rejected (`no_valid_diffs`). Review SHALL run only on configured
triggers, and SHALL never call `/api/combos/test`.

#### Scenario: Reviewer model unavailable
- GIVEN no eligible reviewer model is available
- WHEN the review step runs
- THEN the deterministic combo is applied unchanged with status `skipped_no_model`
