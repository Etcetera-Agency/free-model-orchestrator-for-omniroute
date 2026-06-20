## ADDED Requirements

### Requirement: Production apply invokes the real smoke path

The composed production runtime SHALL invoke the combo applier and its
transactional smoke test when the `apply` stage runs; it SHALL NOT report a
fabricated combo-test signal. The smoke test SHALL exercise the applied `fmo-`
combos through the existing OmniRoute path and SHALL NEVER call
`/api/combos/test`. When the smoke test fails, the runtime SHALL roll back the
applied diff.

#### Scenario: Production apply smoke-tests applied combos
- **WHEN** the production `apply` stage applies a combo diff
- **THEN** the transactional smoke test runs against the applied `fmo-` combos
- **AND** the runtime never calls `/api/combos/test`

#### Scenario: Fabricated smoke signal rejected
- **WHEN** the apply adapter reports the combo-test signal
- **THEN** the signal reflects whether the real smoke test ran
- **AND** a hardcoded or fabricated combo-test signal fails the executable suite
