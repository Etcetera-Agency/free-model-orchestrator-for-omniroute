## ADDED Requirements

### Requirement: Per-endpoint research failures degrade, not abort

The production `quota-research` stage SHALL isolate per-endpoint failures: an
error researching one endpoint SHALL be recorded and that endpoint skipped, and
the stage SHALL continue researching the remaining endpoints rather than
returning on the first error. When one or more endpoints failed, the stage SHALL
report `partial_stale` rather than `external_dependency_failed`, so the run
continues with the endpoints that did succeed.

#### Scenario: One endpoint error does not stop research for the rest
- GIVEN three endpoints need quota research and the second one errors
- WHEN the `quota-research` stage runs
- THEN the first and third endpoints are still researched and persisted
- AND the second endpoint is recorded as failed and skipped

#### Scenario: Per-endpoint failures mark the run partial
- GIVEN at least one endpoint failed during quota research while others succeeded
- WHEN the stage finishes
- THEN it returns `partial_stale`
- AND the run is not failed as `external_dependency_failed`
