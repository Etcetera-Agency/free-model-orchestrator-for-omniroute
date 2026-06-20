## ADDED Requirements

### Requirement: Production quota stage uses the Instructor inspector

The production `quota-research` stage SHALL extract the quota claim through
`run_quota_inspector` over the shared runtime when it is available. When the
inspector is unavailable or returns an unusable claim, the stage SHALL fail open
to the deterministic `extract_summary_claim` path. In both paths the
deterministic validator, `summary_confidence_cap`, and the worsen-quota rule
remain the source of truth; the inspector never raises a claim above what the
deterministic gate allows.

#### Scenario: Inspector path taken when runtime available
- **WHEN** the `quota-research` stage runs with the shared runtime available
- **THEN** the quota claim is extracted via `run_quota_inspector`
- **AND** the resulting rule is still capped by `summary_confidence_cap`

#### Scenario: Fails open to deterministic extraction
- **WHEN** the inspector is unavailable or returns an unusable claim
- **THEN** the stage extracts the claim via `extract_summary_claim`
- **AND** the stage completes without failing the run

#### Scenario: Inspector cannot exceed the deterministic cap
- **WHEN** the inspector returns a confidence above `summary_confidence_cap`
- **THEN** the activated rule is clamped to the cap as opportunistic capacity
