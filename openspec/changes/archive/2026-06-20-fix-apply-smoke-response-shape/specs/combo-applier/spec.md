# combo-applier Specification

## MODIFIED Requirements

### Requirement: Production apply invokes the real smoke path

The composed production runtime SHALL invoke the combo applier and its
transactional smoke test when the `apply` stage runs; it SHALL NOT report a
fabricated combo-test signal. The smoke test SHALL exercise the applied `fmo-`
combos through the existing OmniRoute path and SHALL NEVER call
`/api/combos/test`. When the smoke test fails, the runtime SHALL roll back the
applied diff.

The smoke decision SHALL be derived from the OmniRoute-compatible response, not
from a fabricated body-level field. A smoke POST that completes without raising
(HTTP 2xx, enforced by the OmniRoute client) and returns a non-empty assistant
message (`choices[0].message.content`) SHALL be treated as a smoke pass. A smoke
POST that raises `OmniRouteRequestError` (non-2xx HTTP) or returns an empty or
missing assistant message SHALL be treated as a smoke failure that triggers
rollback. The smoke decision SHALL NOT read a top-level `status_code` field from
the response body.

#### Scenario: Production apply smoke-tests applied combos
- **WHEN** the production `apply` stage applies a combo diff
- **THEN** the transactional smoke test runs against the applied `fmo-` combos
- **AND** the runtime never calls `/api/combos/test`

#### Scenario: Fabricated smoke signal rejected
- **WHEN** the apply adapter reports the combo-test signal
- **THEN** the signal reflects whether the real smoke test ran
- **AND** a hardcoded or fabricated combo-test signal fails the executable suite

#### Scenario: Smoke pass derived from OpenAI-compatible body
- GIVEN a smoke POST returns HTTP 2xx with a non-empty
  `choices[0].message.content`
- WHEN the smoke decision is computed
- THEN the smoke passes without reading any body-level `status_code` field

#### Scenario: Empty completion is a smoke failure
- GIVEN a smoke POST returns HTTP 2xx but the assistant message content is empty
  or missing
- WHEN the smoke decision is computed
- THEN the smoke fails and the applied diff is rolled back

#### Scenario: Non-2xx smoke response is a smoke failure
- GIVEN the smoke POST raises `OmniRouteRequestError` for a non-2xx HTTP status
- WHEN the smoke decision is computed
- THEN the smoke fails and the applied diff is rolled back rather than crashing
