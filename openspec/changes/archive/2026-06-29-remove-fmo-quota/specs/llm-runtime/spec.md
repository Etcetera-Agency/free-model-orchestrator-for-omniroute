# llm-runtime Specification

## MODIFIED Requirements

### Requirement: Uniform Instructor runtime for all LLM sites

The system SHALL run every structured-LLM site through one shared Instructor
runtime configuration (`llm` in config): Hermes role Inspector forecast,
smart-combo-reviewer, and the aa-index migration agent. The shared block SHALL
define transport, endpoint, structured-output mode and retry defaults; each site
SHALL override only call limits and prompt selection unless a site-specific spec
explicitly allows another override. Inspector sites SHALL use one model-selection
approach: they SHALL leave `LlmSiteConfig.model` unset and SHALL rely on the
shared runtime resolver to provide a concrete provider model id at call time. No
Inspector SHALL set `site.model` to a hardcoded fabricated combo route. No
separate agent framework SHALL be used. Advisory sites are fail-open, not out of
scope. FMO SHALL NOT include a quota-research Inspector site.

#### Scenario: Add or change runtime defaults
- GIVEN the shared Instructor transport/retry defaults change in `llm`
- WHEN any structured-LLM site runs
- THEN all sites use the updated defaults without per-site duplication

#### Scenario: Inspector sites use one resolver approach
- GIVEN any Inspector site issues a structured completion
- WHEN the shared runtime resolver selects provider model `provider/model-a`
- THEN the outbound model id is `provider/model-a`
- AND the Inspector site does not set `site.model`
- AND no fabricated Inspector combo is used

#### Scenario: Inspector sites fail closed without a resolver model
- GIVEN any Inspector site issues a structured completion
- AND no resolver-selected provider model is available
- WHEN the shared runtime prepares the call
- THEN it fails closed as `llm_model_unavailable`
- AND no fabricated Inspector combo is used

### Requirement: Shared Instructor + Pydantic runtime adapter

The system SHALL route structured-LLM sites (Hermes role Inspector forecast,
smart-combo-reviewer, AA index migration) through one shared Instructor +
Pydantic runtime adapter: OpenAI SDK → OmniRoute / OpenAI-compatible transport →
model → Instructor → validated Pydantic output. The adapter SHALL apply provider
config, structured-output mode, bounded retries, prompt assembly with secret
redaction, and per-site model limits. Smart-combo-reviewer and AA index
migration SHALL be advisory and fail open — when the LLM is unavailable or
returns nothing usable, the deterministic pipeline SHALL proceed. FMO SHALL NOT
route quota-research Inspector calls.

#### Scenario: All sites use the adapter
- GIVEN any structured-LLM site runs
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

### Requirement: LLM model is selected by criteria from confirmed-free models

The model id substituted into every Instructor call SHALL be selected by the
selection procedure, never a static paid model id and never a dedicated combo
built for the orchestrator. Inspector sites SHALL not provide a site-level model
fallback; they SHALL receive only the concrete provider model id selected by the
runtime resolver. The criterion is the **confirmed-free model with the maximum AA
`intelligence_index`** whose endpoint is healthy and has positive access state.
FMO SHALL NOT perform a fresh live quota/liveness check in the resolver.
Resolution order: (1) the highest-`intelligence_index` healthy confirmed-free
model from the catalog with positive access state, else (2) a manually
configured bootstrap model id that MUST be confirmed free, else (3) no-LLM mode.
The runtime SHALL NOT route an LLM call through a paid or unconfirmed model under
any condition. When resolution yields no confirmed-free model, advisory sites
fail open and the deterministic pipeline proceeds without the LLM.

#### Scenario: Highest-index confirmed-free model selected
- **WHEN** the catalog has healthy confirmed-free models with positive access state
- **THEN** the runtime substitutes the one with the maximum AA `intelligence_index`
- **AND** no dedicated orchestrator combo is created

#### Scenario: Falls to next model by index on unavailability
- **WHEN** the highest-`intelligence_index` confirmed-free model is unhealthy or
  lacks positive access state
- **THEN** the runtime substitutes the next confirmed-free model by descending `intelligence_index`
- **AND** that substitute has positive access state

#### Scenario: Bootstrap model used before any catalog match
- **WHEN** no catalog model yet qualifies but a confirmed-free bootstrap model is configured
- **THEN** the runtime substitutes the bootstrap model

#### Scenario: No confirmed-free model degrades to no-LLM
- **WHEN** neither a qualifying catalog model nor a bootstrap model is available
- **THEN** the runtime enters no-LLM mode and routes no call to a paid model
- **AND** advisory sites fail open and the deterministic pipeline proceeds
