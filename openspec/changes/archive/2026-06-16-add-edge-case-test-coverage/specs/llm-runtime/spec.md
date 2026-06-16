# llm-runtime Specification

## MODIFIED Requirements

### Requirement: No secrets in any prompt

The system SHALL redact PostgreSQL URLs, bearer tokens, cookie assignments, and
secret-like environment/context values whose keys contain `API_KEY`, `TOKEN`,
`SECRET`, or equal `DATABASE_URL`. Secret-like context keys SHALL be omitted
before template interpolation. Any unresolved `{{ placeholder }}` SHALL be
removed from the final prompt.

#### Scenario: PostgreSQL URL redaction
- GIVEN prompt content contains a PostgreSQL URL
- WHEN prompt redaction runs
- THEN the URL is replaced with a redacted marker

#### Scenario: Bearer token redaction
- GIVEN prompt content contains a bearer token
- WHEN prompt redaction runs
- THEN the token is replaced with a redacted marker

#### Scenario: Cookie assignment redaction
- GIVEN prompt content contains a cookie assignment
- WHEN prompt redaction runs
- THEN the cookie value is replaced with a redacted marker

#### Scenario: Secret-like key removal
- GIVEN prompt context contains `DATABASE_URL`, `API_KEY`, `TOKEN`, or `SECRET` keys
- WHEN prompt context is prepared
- THEN those keys are not interpolated

#### Scenario: Unresolved placeholder cleanup
- GIVEN rendered prompt content still contains an unresolved `{{ placeholder }}`
- WHEN prompt assembly finishes
- THEN the unresolved placeholder is removed
