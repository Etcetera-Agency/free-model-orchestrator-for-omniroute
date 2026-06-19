## ADDED Requirements

### Requirement: Apply preconditions evaluated at the entrypoint

The entrypoint SHALL compute apply preconditions by evaluating the apply guard —
database availability, a saved snapshot, a valid desired state, quota safety, and
a passing probe/smoke result — and SHALL pass that computed value into CLI
dispatch instead of a hardcoded value. The evaluation SHALL fail closed: any
unknown, stale, or unavailable input yields preconditions `False`.

#### Scenario: Failing guard input blocks apply
- **WHEN** any apply-guard input is failing, unknown, or stale at the entrypoint
- **THEN** apply preconditions are `False`
- **AND** `apply` exits with code 5 (unsafe) and changes nothing

#### Scenario: Healthy guard inputs allow apply
- **WHEN** every apply-guard input is healthy at the entrypoint
- **THEN** apply preconditions are `True`
- **AND** `apply` is allowed to proceed through the runner's gating
