# llm-runtime Specification

## Purpose
TBD - created by archiving change add-foundation. Update Purpose after archive.
## Requirements
### Requirement: Uniform Instructor runtime for all LLM sites

The system SHALL run every structured-LLM site through one shared Instructor
runtime configuration (`llm` in config): quota-research inspector, Hermes role
Inspector forecast, smart-combo-reviewer, and the aa-index migration agent. The
shared block SHALL define transport, endpoint, structured-output mode and retry
defaults; each site SHALL override only call limits and prompt selection unless a
site-specific spec explicitly allows another override. All Inspector sites SHALL
use one model-selection approach: they SHALL leave `LlmSiteConfig.model` unset
and SHALL rely on the shared runtime resolver to provide a concrete provider
model id at call time. No Inspector SHALL set `site.model` to a hardcoded
fabricated combo route. No separate agent framework SHALL be used. All four
structured-LLM sites are part of the project; advisory sites are fail-open, not
out of scope.

#### Scenario: Add or change runtime defaults
- GIVEN the shared Instructor transport/retry defaults change in `llm`
- WHEN any of the four sites runs
- THEN all four use the updated defaults without per-site duplication

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

### Requirement: Externalized, independently editable prompts

The system SHALL load each LLM site's prompt from its own file under
`llm.prompts_dir` (one file per use case), including the `aa-index-migration`
site. Editing one site's prompt file SHALL NOT require code changes or edits to
any other site's prompt. Every wired LLM site that has a configured prompt file
SHALL pass that file to shared prompt assembly through `LlmSiteConfig.prompt_path`
or an equivalent shared-runtime site configuration, so prompt redaction,
placeholder interpolation, unresolved placeholder cleanup, and prompt length
limits apply uniformly.

#### Scenario: Edit one prompt
- GIVEN an operator edits `prompts/smart-combo-reviewer.md`
- WHEN the reviewer next runs
- THEN it uses the edited prompt and no other site's prompt or behavior changes

#### Scenario: AA migration prompt is loaded from file
- GIVEN an operator edits `prompts/aa-index-migration.md`
- WHEN `aa-index analyze` next prepares the migration Instructor call
- THEN it uses the edited prompt through the shared prompt assembly path
- AND no code change is required for the prompt edit to take effect

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

### Requirement: Production Instructor client is constructed and shared

The composed runtime SHALL construct the shared Instructor client via
`instructor.from_openai` from validated startup config and provide it, wrapped in
`SharedInstructorRuntime`, to every wired LLM site. The client SHALL target the
OmniRoute OpenAI-compatible `/v1` surface derived from `OMNIROUTE_URL` and
authenticate with the configured api key; the per-call model is supplied by the
selection procedure (see the model-selection requirement). Structured output
SHALL be produced through Instructor with a Pydantic `response_model`.
Startup validation SHALL fail closed when required LLM provider config is missing
or malformed. No site SHALL call a model through any path other than this shared
runtime.

#### Scenario: Client built from config
- **WHEN** the production composition is assembled from validated config
- **THEN** the Instructor client is constructed via `instructor.from_openai` with
  the OmniRoute `/v1` base URL and the configured api key
- **AND** the wired sites receive the wrapping runtime rather than a test stub

#### Scenario: Missing LLM provider config fails closed
- **WHEN** startup validation runs without required LLM provider config
- **THEN** validation fails with `validation_failed` and the pipeline does not start

#### Scenario: No site bypasses the shared runtime
- **WHEN** any wired structured-LLM site issues a call
- **THEN** it goes through the shared runtime transport
- **AND** a site constructing its own transport fails the suite

### Requirement: LLM model is selected by criteria from confirmed-free models

The model id substituted into every Instructor call SHALL be selected by the
selection procedure, never a static paid model id and never a dedicated combo
built for the orchestrator. Inspector sites SHALL not provide a site-level model
fallback; they SHALL receive only the concrete provider model id selected by the
runtime resolver. The criterion is the **confirmed-free model with the maximum AA
`intelligence_index`** whose endpoint is healthy and has remaining quota. Before
returning a candidate model id, the resolver SHALL perform a fresh live
quota/liveness check for that candidate. A candidate whose live check shows
`percentRemaining <= 10`, a `resetAt` in the future, or exhausted
`quotaTotal`/`quotaUsed` SHALL be skipped; if the live check is unavailable or
does not prove usable remaining quota, that candidate SHALL also be skipped. The
LLM resolver's minimum live remaining threshold SHALL be 10%, independent of the
lower apply-stage liveness floor. On unavailability the runtime SHALL fall to the
next confirmed-free model by descending `intelligence_index` and repeat the fresh
live check.
Resolution order: (1) the highest-`intelligence_index` healthy confirmed-free
model from the catalog whose fresh live quota/liveness check passes, else (2) a
manually configured bootstrap model id that MUST be confirmed free and whose
fresh live quota/liveness check passes, else (3) no-LLM mode. The runtime SHALL
NOT route an LLM call through a paid, unconfirmed, exhausted, or locked-out model
under any condition. When resolution yields no confirmed-free model with fresh
usable quota, advisory sites fail open and the deterministic pipeline proceeds
without the LLM.

#### Scenario: Highest-index confirmed-free model selected
- **WHEN** the catalog has healthy confirmed-free models
- **AND** the highest-index candidate's fresh live quota/liveness check passes
- **THEN** the runtime substitutes the one with the maximum AA `intelligence_index`
- **AND** no dedicated orchestrator combo is created

#### Scenario: Falls to next model by index on unavailability
- **WHEN** the highest-`intelligence_index` confirmed-free model is unhealthy,
  exhausted, locked out, has `percentRemaining <= 10`, or lacks a passing fresh
  live quota/liveness check
- **THEN** the runtime substitutes the next confirmed-free model by descending `intelligence_index`
- **AND** that substitute has passed its own fresh live quota/liveness check

#### Scenario: Bootstrap model used before any catalog match
- **WHEN** no catalog model yet qualifies but a confirmed-free bootstrap model is configured
- **AND** the bootstrap model's fresh live quota/liveness check passes
- **THEN** the runtime substitutes the bootstrap model

#### Scenario: No confirmed-free model degrades to no-LLM
- **WHEN** neither a qualifying catalog model nor a bootstrap model is available
  with a passing fresh live quota/liveness check
- **THEN** the runtime enters no-LLM mode and routes no call to a paid model
- **AND** advisory sites fail open and the deterministic pipeline proceeds

#### Scenario: Just-consumed quota is not selected
- **GIVEN** the database still shows remaining quota for provider model
  `provider/model-a`
- **AND** the fresh live quota/liveness check shows `provider/model-a` is
  exhausted, locked out, or at `percentRemaining <= 10` now
- **WHEN** the runtime resolver selects a model for an Instructor call
- **THEN** `provider/model-a` is skipped
- **AND** the resolver tries the next eligible confirmed-free model
