# quota-research Specification Delta

## ADDED Requirements

### Requirement: Inspector resolves a reported range using the prior limit

The Instructor inspector SHALL collapse a quota reported as a range `[low, high]`
into a single `amount` within that range, anchored to the previously trusted
limit. The system SHALL thread `previous_limit` into the inspector path so it is
available to the inspector prompt. The inspector SHALL return the value in
`[low, high]` closest to `previous_limit` (the prior limit clamped into the
range); when `previous_limit` is unknown, the inspector SHALL return the
conservative lower bound `low`. The deterministic validator,
`summary_confidence_cap`, and the worsen-quota safe-mode rule remain the source of
truth; range resolution only selects a value within the evidence bounds and never
raises a claim above what the gate allows.

#### Scenario: Prior limit inside the range is kept
- GIVEN a snapshot range of `[low, high]` and a `previous_limit` within it
- WHEN the inspector resolves the claim
- THEN the resolved amount equals `previous_limit`

#### Scenario: Range below the prior limit resolves to its upper bound
- GIVEN a snapshot range entirely below `previous_limit` (a downgrade)
- WHEN the inspector resolves the claim
- THEN the resolved amount equals the range's upper bound `high`

#### Scenario: Range above the prior limit resolves to its lower bound
- GIVEN a snapshot range entirely above `previous_limit` (an unverified upgrade)
- WHEN the inspector resolves the claim
- THEN the resolved amount equals the range's lower bound `low`

#### Scenario: No prior limit resolves conservatively
- GIVEN a snapshot range of `[low, high]` and no `previous_limit`
- WHEN the inspector resolves the claim
- THEN the resolved amount equals the conservative lower bound `low`

#### Scenario: Prior limit reaches the inspector prompt
- GIVEN quota research runs with a `previous_limit` and an available inspector
- WHEN extraction is delegated to the inspector
- THEN the configured prompt file's `{{previous_limit}}` placeholder resolves to
  that value in the assembled prompt

## MODIFIED Requirements

### Requirement: Production quota stage uses the Instructor inspector

The production `quota-research` stage SHALL extract the quota claim through
`run_quota_inspector` over the shared runtime when it is available. The quota
inspector SHALL NOT set `site.model` to any hardcoded fabricated combo. It SHALL
leave the model unset so the shared runtime resolver selects a concrete provider
model at call time. In production that resolver is `select_llm_model`, which
returns the selected free provider model's `provider_model_id`. When no
resolver-selected provider model is available, the adapter SHALL fail closed as
`llm_model_unavailable` instead of calling a fabricated inspector combo. When
the inspector is unavailable or returns an
unusable claim, the stage SHALL fail open to the deterministic
`extract_summary_claim` path. In both paths the deterministic validator,
`summary_confidence_cap`, and the worsen-quota rule remain the source of truth;
the inspector never raises a claim above what the deterministic gate allows.

#### Scenario: Inspector path taken when runtime available
- **WHEN** the `quota-research` stage runs with the shared runtime available
- **THEN** the quota claim is extracted via `run_quota_inspector`
- **AND** the resulting rule is still capped by `summary_confidence_cap`

#### Scenario: Inspector uses resolver-selected provider model
- **GIVEN** the shared runtime resolver selects provider model `provider/model-a`
- **WHEN** `run_quota_inspector` calls the Instructor runtime
- **THEN** the outbound model id is `provider/model-a`
- **AND** no fabricated Inspector combo is used

#### Scenario: Resolver-less inspector fails closed
- **GIVEN** no resolver-selected provider model is available
- **WHEN** `run_quota_inspector` calls the Instructor runtime
- **THEN** the call fails closed as `llm_model_unavailable`
- **AND** no fabricated Inspector combo is used

#### Scenario: Fails open to deterministic extraction
- **WHEN** the inspector is unavailable or returns an unusable claim
- **THEN** the stage extracts the claim via `extract_summary_claim`
- **AND** the stage completes without failing the run

#### Scenario: Inspector cannot exceed the deterministic cap
- **WHEN** the inspector returns a confidence above `summary_confidence_cap`
- **THEN** the activated rule is clamped to the cap as opportunistic capacity
