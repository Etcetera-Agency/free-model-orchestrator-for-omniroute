# quality-gate Specification

## ADDED Requirements

### Requirement: Single optional gate as hard pre-filter

The system SHALL support at most one minimum quality gate per role (`metric` in
`intelligence_index | coding_index | agentic_index`, plus `value`) and SHALL
apply it as a hard filter before weighted scoring; endpoints below the gate are
excluded from the role. Weighted scoring only orders endpoints that passed.

#### Scenario: Below the gate
- GIVEN a role gate `agentic_index >= 45` and an endpoint with `agentic_index = 30`
- WHEN eligibility runs
- THEN the endpoint is excluded from that role before weighted scoring

### Requirement: Unverifiable gate handling

If the gate metric is missing for an endpoint the system SHALL set
`quality_gate_status = unverifiable` and exclude the endpoint from the role
unless `allow_unverified_quality_gate` is set.

#### Scenario: Missing gate metric
- GIVEN a role gate on `coding_index` and an endpoint with no coding index
- WHEN the gate is evaluated and override is off
- THEN the endpoint is excluded as unverifiable

### Requirement: Index-version binding

Each gate SHALL store `metric`, `value` and `index_version` and apply only to the
matching Artificial Analysis index version. On a major index change the gate is
marked `needs_recalibration`, new allocation plans are not applied with an
unverified gate, and the previous combo is kept until thresholds update.

#### Scenario: Major index change
- GIVEN a gate bound to index version v1 and a new major index v2 arrives
- WHEN scoring runs
- THEN the v1 raw threshold is not applied to v2 and the current combo is kept
