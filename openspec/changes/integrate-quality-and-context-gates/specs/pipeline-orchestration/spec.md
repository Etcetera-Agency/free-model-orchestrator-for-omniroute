# pipeline-orchestration Specification

## ADDED Requirements

### Requirement: Scoring stage applies context and quality hard filters

The composed runtime's `role-scoring` stage SHALL apply the
context-window-eligibility and quality-gate hard filters as part of its
production eligibility path before persisting scores. Endpoints below a role's
context-window minimum (effective context = min of known sources, unknown
excluded unless the role overrides) and endpoints failing or unverifiable
against the role's optional quality gate (unless the role allows unverified)
SHALL NOT receive a persisted score for that role. On an Artificial Analysis
index-version mismatch the gate SHALL be treated as `needs_recalibration`: no new
plan is applied for that role and the current combo is kept. The persisted
rejection reason SHALL distinguish context and quality exclusions.

#### Scenario: Scoring stage drops below-context endpoint
- **WHEN** the `role-scoring` stage runs and an endpoint is below the role
  context minimum
- **THEN** no score row is persisted for that endpoint/role
- **AND** the persisted rejection reason identifies the context filter

#### Scenario: Scoring stage drops below-gate endpoint
- **WHEN** the `role-scoring` stage runs and an endpoint is below the role
  quality gate
- **THEN** no score row is persisted for that endpoint/role
- **AND** the persisted rejection reason identifies the quality gate

#### Scenario: Index-version mismatch keeps current combo
- **WHEN** the `role-scoring` stage runs against a quality gate bound to a stale
  index version
- **THEN** the gate is marked `needs_recalibration`
- **AND** no new allocation plan is applied for that role
