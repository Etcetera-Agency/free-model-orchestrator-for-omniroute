# hermes-inventory Specification

## Purpose
TBD - created by archiving change add-role-lifecycle. Update Purpose after archive.
## Requirements
### Requirement: Daily and unknown-role inventory

The system SHALL run a full Hermes inventory daily, and SHALL run an immediate
full inventory (never a partial single-agent lookup) whenever a role name appears
in Hermes usage, cron, config or an OmniRoute request that is absent from the
registry.

#### Scenario: Unknown role observed
- GIVEN an OmniRoute request references a role not in the registry
- WHEN the orchestrator detects it
- THEN it runs a full Hermes inventory immediately, not a partial scan

### Requirement: Consumer registry

The system SHALL store, per role, every Hermes consumer that uses it together with
its schedule/cadence, expected frequency and calls_per_run, and SHALL NOT derive
roles from runtime history as the primary mechanism. Consumer surfaces are the
real Hermes triggers (collectively called "routines"):

- `agent_profile` — an interactive agent profile (manual/continuous);
- `cron_job` — a scheduled job (cron expression or human-readable interval);
- `webhook` — a webhook subscription, covering both GitHub event triggers and API
  triggers (event-driven; forecast from observed rate / configured bootstrap);
- `service` — a long-running service (continuous).

#### Scenario: Mixed consumers recorded
- GIVEN a role used by one agent profile, one cron job and one webhook subscription
- WHEN the inventory runs
- THEN all three consumers are stored with their cadence and calls_per_run

#### Scenario: Event-driven consumer cadence
- GIVEN a role used only by a webhook (API trigger) with no fixed schedule
- WHEN its demand is recorded
- THEN cadence comes from observed rate or configured bootstrap, not a cron schedule

### Requirement: Adapters and environment

The system SHALL support filesystem, command and http inventory adapters that all
normalize to one internal schema; paths, URLs and tokens come only from
environment variables; missing required variables SHALL fail startup with a clear
error.

#### Scenario: Missing required env
- GIVEN the selected adapter mode lacks a required environment variable
- WHEN the service starts
- THEN startup fails with a clear error

### Requirement: Change-driven forecast refresh

The system SHALL diff each inventory against the previous one and, when consumers
or frequency change, mark the forecast stale, re-run the Inspector forecast, run
allocation, and rebuild a combo only if the resulting allocation changed
materially.

#### Scenario: Schedule changed
- GIVEN a cron job's schedule changed since the last inventory
- WHEN the diff is processed
- THEN the role forecast is refreshed and allocation re-runs

### Requirement: Deterministic gathering; Inspector is prompt-only

Deterministic code SHALL enumerate consumers, read Hermes state, compute the
inventory diff and assemble the complete Inspector prompt. The Inspector SHALL
NOT read Hermes files, query state, or detect what changed; it receives a single
pre-assembled prompt containing all gathered information and returns only a
forecast.

#### Scenario: Inspector does not inspect
- GIVEN consumers and changes have been gathered by deterministic code
- WHEN the Inspector is invoked
- THEN it is given one assembled prompt and does not itself read files or diff state

### Requirement: Inspector runs via Instructor with limited scope

The Hermes role Inspector SHALL run through the same Instructor runtime as the
other structured-LLM steps (OpenAI SDK → OmniRoute → model → Instructor →
validated Pydantic forecast) and SHALL return only a forecast (runs, calls,
tokens, concurrency, confidence, assumptions); it SHALL NOT select models or
change quota attribution, and SHALL receive no secrets in its prompt.

#### Scenario: Inspector output
- GIVEN the Inspector is asked to forecast a role
- WHEN it responds via Instructor
- THEN it returns a validated forecast only, with no model choice or quota change

