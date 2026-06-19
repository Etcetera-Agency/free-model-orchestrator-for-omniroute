## ADDED Requirements

### Requirement: Runtime docs reflect shipped and planned state

The project documentation SHALL distinguish shipped runtime behavior from
planned OpenSpec slices, and SHALL NOT mark archived changes as active.
Executable scenario coverage documentation SHALL describe how scenarios move out
of the pending allowlist.

#### Scenario: Active docs state
- GIVEN project docs describe OpenSpec change status and executable scenario coverage
- WHEN runtime docs are aligned
- THEN archived changes are not described as active
- AND uncovered scenarios are represented either by active OpenSpec changes or by an empty pending allowlist
