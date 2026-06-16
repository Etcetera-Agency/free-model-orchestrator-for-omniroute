# llm-runtime Specification

## Purpose
TBD - created by archiving change add-foundation. Update Purpose after archive.
## Requirements
### Requirement: Uniform Instructor runtime for all LLM sites

The system SHALL run every structured-LLM site through one shared Instructor
runtime configuration (`llm` in config): quota-research inspector, Hermes role
Inspector forecast, smart-combo-reviewer, and the aa-index migration agent. The
shared block SHALL define transport, endpoint, structured-output mode and retry
defaults; each site SHALL override only its model selection and call limits. No
separate agent framework SHALL be used. All four are part of the project; sites
3–4 are advisory/fail-open, not out of scope.

#### Scenario: Add or change runtime defaults
- GIVEN the shared Instructor transport/retry defaults change in `llm`
- WHEN any of the four sites runs
- THEN all four use the updated defaults without per-site duplication

### Requirement: Externalized, independently editable prompts

The system SHALL load each LLM site's prompt from its own file under
`llm.prompts_dir` (one file per use case). Editing one site's prompt file SHALL
NOT require code changes or edits to any other site's prompt.

#### Scenario: Edit one prompt
- GIVEN an operator edits `prompts/smart-combo-reviewer.md`
- WHEN the reviewer next runs
- THEN it uses the edited prompt and no other site's prompt or behavior changes

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
