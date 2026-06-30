# role-scorer Specification

## Purpose
Preserve static router recognition used by role policy and profile normalization.

## Requirements

### Requirement: Router configuration remains recognizable
FMO SHALL keep static router-tail recognition for role policy/profile
normalization even though endpoint scoring is no longer local.

#### Scenario: Configured router is recognized
- **WHEN** a configured router id is checked
- **THEN** it is recognized case-insensitively.

#### Scenario: Unlisted model is not a router
- **WHEN** an unconfigured model id is checked
- **THEN** it is not treated as a router.

#### Scenario: Child router is independent of its parent
- **WHEN** one router id shares a provider prefix with another id
- **THEN** only exact configured ids match.
