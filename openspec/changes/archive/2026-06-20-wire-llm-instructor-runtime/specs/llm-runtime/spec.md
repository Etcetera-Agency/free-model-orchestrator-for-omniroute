## ADDED Requirements

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
built for the orchestrator. The criterion is the **confirmed-free model with the
maximum AA `intelligence_index`** whose endpoint is healthy and has remaining
quota; on unavailability the runtime SHALL fall to the next confirmed-free model
by descending `intelligence_index`. Resolution order: (1) the highest-`intelligence_index`
healthy confirmed-free model from the catalog, else (2) a manually configured
bootstrap model id that MUST be confirmed free, else (3) no-LLM mode. The runtime
SHALL NOT route an LLM call through a paid or unconfirmed model under any
condition. When resolution yields no confirmed-free model, advisory sites fail
open and the deterministic pipeline proceeds without the LLM.

#### Scenario: Highest-index confirmed-free model selected
- **WHEN** the catalog has healthy confirmed-free models
- **THEN** the runtime substitutes the one with the maximum AA `intelligence_index`
- **AND** no dedicated orchestrator combo is created

#### Scenario: Falls to next model by index on unavailability
- **WHEN** the highest-`intelligence_index` confirmed-free model is unhealthy or out of quota
- **THEN** the runtime substitutes the next confirmed-free model by descending `intelligence_index`

#### Scenario: Bootstrap model used before any catalog match
- **WHEN** no catalog model yet qualifies but a confirmed-free bootstrap model is configured
- **THEN** the runtime substitutes the bootstrap model

#### Scenario: No confirmed-free model degrades to no-LLM
- **WHEN** neither a qualifying catalog model nor a bootstrap model is available
- **THEN** the runtime enters no-LLM mode and routes no call to a paid model
- **AND** advisory sites fail open and the deterministic pipeline proceeds
