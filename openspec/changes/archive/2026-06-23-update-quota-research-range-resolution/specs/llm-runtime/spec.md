# llm-runtime Specification Delta

## MODIFIED Requirements

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
