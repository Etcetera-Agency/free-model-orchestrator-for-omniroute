# hermes-inventory Specification

## Purpose
TBD - created by archiving change add-role-lifecycle. Update Purpose after archive.
## Requirements
### Requirement: Daily and event-triggered inventory

The system SHALL run a full Hermes inventory daily. Manual or event-driven runs
MAY request a full Hermes inventory, but an unknown role name alone SHALL NOT
force an immediate inventory run or create a new combo.

### Requirement: Consumer registry

The system SHALL store, per role, every Hermes consumer that uses it together with
its schedule/cadence, expected frequency and calls_per_run, and SHALL NOT derive
roles from runtime history as the primary mechanism. Consumer surfaces are read
from the **real Hermes sources** (NousResearch/hermes-agent), not a fabricated
intermediate schema:

- `cron_job` — each job in `~/.hermes/cron/jobs.json` (`{"jobs": [...]}`); cadence
  comes from the job `schedule` object (`{"kind": "interval", "minutes": N}`,
  `{"kind": "cron", "expr": ...}`, or `{"kind": "once", ...}`) and the routed role
  from the job `model`, which is the OmniRoute **combo** the routine routes to
  (one combo per role, so the combo id is the role key), defaulting to the
  gateway default combo's role when null;
- `webhook` — each route in `~/.hermes/webhook_subscriptions.json`; cadence is
  event-driven, derived from the subscription `events` (or observed rate /
  bootstrap when no fixed schedule);
- `agent_profile` — an interactive Hermes profile whose gateway is not running;
- `service` — a Hermes profile whose gateway is running (long-running);

The Hermes `model` field is an OmniRoute combo id, not a raw model. Runtime
demand (observed `calls_per_run` per role) SHALL be read from the real
`~/.hermes/state.db` `sessions` table (`AVG(api_call_count)` grouped by `model`,
where `sessions.model` is likewise the combo the session ran against), and
consumers without observed history SHALL fall back to a conservative bootstrap
value rather than zero.

#### Scenario: Mixed consumers recorded
- GIVEN a role used by one agent profile, one cron job and one webhook subscription
- WHEN the inventory runs
- THEN all three consumers are stored with their cadence and calls_per_run

#### Scenario: Real cron job schedule mapped
- GIVEN a `~/.hermes/cron/jobs.json` job with `schedule.kind` of `cron` or `interval`
- WHEN the cron source is parsed
- THEN a `cron_job` consumer is recorded with cadence taken from the cron `expr` or interval display
- AND a disabled (paused) job is excluded from active demand

#### Scenario: Profile gateway state selects consumer type
- GIVEN a Hermes profile listing where one profile has a running gateway and another does not
- WHEN the profile source is parsed
- THEN the running-gateway profile is recorded as a `service`
- AND the other profile is recorded as an `agent_profile`

#### Scenario: Event-driven consumer cadence
- GIVEN a role used only by a webhook (API trigger) with no fixed schedule
- WHEN its demand is recorded
- THEN cadence comes from observed rate or configured bootstrap, not a cron schedule

#### Scenario: Observed calls_per_run from state.db
- GIVEN runtime sessions exist in `~/.hermes/state.db` for a role's model
- WHEN the inventory is built with the session connection
- THEN that role's `calls_per_run` is the average `api_call_count` of those sessions
- AND a role with no observed sessions keeps the conservative bootstrap value

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

### Requirement: Hermes command/http adapters and live enumeration

The system SHALL provide command and http Hermes inventory adapters that return
the same real source shapes as the filesystem reader and raise structured errors
on failure. Profiles SHALL be enumerated live by scanning the real profile
directories and reading each profile's `config.yaml` model (the OmniRoute combo),
instead of relying on a caller-supplied profile listing. `service` consumers SHALL
be derived from the enabled Hermes gateway platforms configuration.

#### Scenario: Command adapter returns real shapes
- GIVEN the command inventory adapter is configured
- WHEN it runs
- THEN it returns the real cron/webhook/profile/session shapes
- AND a command failure raises a structured error

#### Scenario: Live profile enumeration
- GIVEN real profile directories exist with `config.yaml` model values
- WHEN the inventory enumerates profiles
- THEN each profile is discovered by scanning the directories
- AND its routed role comes from the profile's configured combo

#### Scenario: Service from gateway config
- GIVEN the Hermes gateway platforms configuration enables a long-running platform
- WHEN the inventory runs
- THEN a `service` consumer is recorded for it

### Requirement: Hermes inventory is gathered in production

The production pipeline SHALL run a `hermes-inventory` stage that gathers the
role registry, consumers, schedules, and observed `calls_per_run` through the
deterministic adapter selected by `HERMES_INVENTORY_MODE`, and persist them
through the repository. The Inspector forecast SHALL run prompt-only over the
shared runtime and SHALL NOT read Hermes sources itself. Missing required Hermes
env SHALL fail closed; an unknown role SHALL bootstrap through the dynamic-role
path. The stage SHALL report `success` only when inventory rows are persisted.

#### Scenario: Inventory persisted from the selected mode
- **WHEN** the `hermes-inventory` stage runs with `HERMES_INVENTORY_MODE` set
- **THEN** roles, consumers, schedules, and observed cadence are gathered via the
  matching adapter and persisted
- **AND** an adapter returning success without persisting inventory fails the suite

#### Scenario: Inspector is prompt-only
- **WHEN** the Inspector forecast runs
- **THEN** it receives only the assembled prompt over the shared runtime
- **AND** it performs no direct source reads

#### Scenario: Missing Hermes env fails closed
- **WHEN** required Hermes env is missing
- **THEN** the stage fails closed and no inventory is written

### Requirement: Model slots are read from per-profile config

The system SHALL read every Hermes profile's model slots from that profile's own
`<profile_dir>/config.yaml`, not from the `hermes profile list` summary. The
profile list (`ProfileInfo`) SHALL be used only to enumerate profile name, path
and `gateway_running`; it does not carry auxiliary slots and therefore is not the
slot source.

The reader SHALL resolve the main combo from the `model` key in two shapes: a
mapping (`model.default` is the combo id) and the legacy bare string. An
unconfigured profile whose `model` is the empty-string sentinel `""` SHALL yield
no main combo without error. The reader SHALL carry the raw `auxiliary` mapping
through unchanged for downstream consumer enumeration.

#### Scenario: Model slots are read from per-profile config
- GIVEN a profile whose `config.yaml` sets `model.default` to a combo id
- WHEN the inventory reads that profile
- THEN the main combo is taken from `config.yaml` (`model.default`), not from the
  profile-list summary `model` field
- AND the profile's `auxiliary` mapping is available unchanged to later stages

#### Scenario: Auxiliary slots are absent from the profile list
- GIVEN the `hermes profile list` summary (`ProfileInfo`) for a profile that has
  an `auxiliary:` block in its `config.yaml`
- WHEN the inventory enumerates profiles
- THEN the list summary is used only for name, path and gateway state
- AND the auxiliary slots are obtained from the profile's `config.yaml`, since
  the list summary carries none

#### Scenario: Unconfigured profile model is tolerated
- GIVEN a fresh profile whose `config.yaml` has `model: ""`
- WHEN the inventory reads that profile
- THEN the main combo resolves to none without raising
- AND the profile is still enumerated for its auxiliary slots and gateway state

### Requirement: Auxiliary model slots are consumers

The system SHALL emit a consumer for each profile's main combo and for each
profile `auxiliary.<slot>` whose route resolves to an OmniRoute combo other than
the main combo. An auxiliary slot whose `provider` is `auto` or whose `model` is
empty SHALL NOT produce a separate consumer, because it falls back to the
profile's main combo, which is already counted.

Auxiliary consumers SHALL carry `consumer_type = auxiliary`, a `consumer` key of
`"{profile}:{slot}"`, and the slot name so downstream stages can derive the
slot's capability. Auxiliary overrides configured at the gateway or per-platform
level SHALL be emitted the same way, keyed by `"gateway:{platform}:{slot}"`.

#### Scenario: Auxiliary override becomes a consumer
- GIVEN a profile whose `config.yaml` has `auxiliary.vision` pointing at an
  OmniRoute combo distinct from the main combo
- WHEN the inventory runs
- THEN an `auxiliary` consumer is recorded for that combo keyed `"{profile}:vision"`

#### Scenario: Auto auxiliary slot is not a separate consumer
- GIVEN an `auxiliary.compression` slot with `provider: auto` or empty `model`
- WHEN the inventory runs
- THEN no separate consumer is recorded for that slot
- AND its load is attributed to the profile's main combo consumer

#### Scenario: Gateway auxiliary overrides are consumers
- GIVEN a gateway config with a top-level or per-platform `auxiliary` override to
  a distinct combo
- WHEN the gateway source is parsed
- THEN an `auxiliary` consumer is recorded keyed `"gateway:{platform}:{slot}"`
