# role-scorer Specification

## MODIFIED Requirements

### Requirement: Eligibility filter precedes scoring

The system SHALL score an endpoint for a role only if it has an allowed free
access status, passed the basic probe, has sufficient usable quota greater than
zero, is matched to a canonical model, has a closed breaker, supports the role's
required capabilities, satisfies the role's context-window minimum, and passes
the role's optional quality gate. The context-window and quality-gate hard
filters SHALL be applied in the production scoring path (not only as standalone
functions), before weighted scoring. Each rejection branch SHALL expose a
distinct reason.

#### Scenario: Breaker not closed
- GIVEN an otherwise eligible endpoint whose breaker is not closed
- WHEN scoring eligibility runs
- THEN it is rejected with a breaker reason

#### Scenario: Zero quota boundary
- GIVEN an endpoint has usable quota equal to zero
- WHEN scoring eligibility runs
- THEN it is rejected with a quota reason

#### Scenario: Missing required capability
- GIVEN an endpoint lacks a role-required capability
- WHEN scoring eligibility runs
- THEN it is rejected with a capability reason

#### Scenario: Below context minimum rejected in scoring
- GIVEN an otherwise eligible endpoint whose effective context window is below
  the role minimum
- WHEN the production scoring eligibility runs
- THEN it is rejected with a context reason before weighted scoring

#### Scenario: Below quality gate rejected in scoring
- GIVEN a role with a quality gate and an otherwise eligible endpoint below it
- WHEN the production scoring eligibility runs
- THEN it is rejected with a quality-gate reason before weighted scoring
