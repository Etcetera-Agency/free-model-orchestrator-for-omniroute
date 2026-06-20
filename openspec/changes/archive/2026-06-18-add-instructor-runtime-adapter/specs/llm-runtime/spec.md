## ADDED Requirements

### Requirement: Shared Instructor + Pydantic runtime adapter

The system SHALL route all four structured-LLM sites (quota-research inspector,
Hermes role Inspector forecast, smart-combo-reviewer, AA index migration) through
one shared Instructor + Pydantic runtime adapter: OpenAI SDK → OmniRoute /
OpenAI-compatible transport → model → Instructor → validated Pydantic output. The
adapter SHALL apply provider config, structured-output mode, bounded retries,
prompt assembly with secret redaction, and per-site model limits. Smart-combo-
reviewer and AA index migration SHALL be advisory and fail open — when the LLM is
unavailable or returns nothing usable, the deterministic pipeline SHALL proceed.

#### Scenario: All sites use the adapter
- GIVEN any of the four structured-LLM sites runs
- WHEN it requests a structured completion
- THEN it goes through the shared adapter and returns a validated Pydantic object
- AND the prompt is redacted of secrets and bounded by the per-site model limit

#### Scenario: Advisory site fails open
- GIVEN smart-combo-reviewer or AA index migration calls the adapter
- WHEN the LLM is unavailable or returns nothing usable
- THEN the deterministic pipeline proceeds without the advice

#### Scenario: Malformed completion repaired or rejected
- GIVEN the model returns a malformed structured completion
- WHEN the adapter validates it
- THEN the deterministic validator/repair path runs
- AND an unrepairable result is handled as a deterministic failure, not silently accepted
