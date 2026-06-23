# hermes-inventory Specification

## Purpose
TBD - created by archiving change add-role-lifecycle. Update Purpose after archive.
## Requirements
### Requirement: Daily and event-triggered inventory

The system SHALL run a full Hermes inventory daily. Manual or event-driven runs
MAY request a full Hermes inventory, but an unknown role name alone SHALL NOT
force an immediate inventory run or create a new combo.

#### Scenario: Daily run performs full inventory
- GIVEN the daily scheduler reaches the Hermes inventory window
- WHEN the inventory trigger is evaluated
- THEN a full Hermes inventory is requested

#### Scenario: Manual run can request full inventory
- GIVEN an operator starts a manual run with full Hermes inventory requested
- WHEN the inventory trigger is evaluated
- THEN a full Hermes inventory is requested

#### Scenario: Unknown role event does not create inventory or combo
- GIVEN an event-driven run references an unknown role name
- AND no explicit full inventory request is present
- WHEN the inventory trigger is evaluated
- THEN no immediate inventory run is forced by that role name alone
- AND no new combo is created from the unknown role name

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
change quota attribution, and SHALL receive no secrets in its prompt. The Hermes
forecast Inspector and Hermes intelligence Inspector SHALL NOT set `site.model`
to any hardcoded fabricated combo. They SHALL leave the model unset so the shared
runtime resolver selects a concrete provider model at call time. In production
that resolver is `select_llm_model`, which returns the selected free provider
model's `provider_model_id`. When no resolver-selected provider model is
available, the adapter SHALL fail closed as `llm_model_unavailable` instead of
calling a fabricated inspector combo.

#### Scenario: Inspector output
- GIVEN the Inspector is asked to forecast a role
- WHEN it responds via Instructor
- THEN it returns a validated forecast only, with no model choice or quota change

#### Scenario: Inspector uses resolver-selected provider model
- GIVEN the shared runtime resolver selects provider model `provider/model-a`
- WHEN the Hermes forecast Inspector or Hermes intelligence Inspector calls the
  Instructor runtime
- THEN the outbound model id is `provider/model-a`
- AND no fabricated Inspector combo is used

#### Scenario: Resolver-less inspector fails closed
- GIVEN no resolver-selected provider model is available
- WHEN the Hermes forecast Inspector or Hermes intelligence Inspector calls the
  Instructor runtime
- THEN the call fails closed as `llm_model_unavailable`
- AND no fabricated Inspector combo is used

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

### Requirement: Per-role intelligence Inspector

The system SHALL run a second, advisory Inspector — distinct from the demand
Inspector — that estimates the **quality anchor** for each role: which AA axis
(`intelligence_index`, `coding_index`, or `agentic_index`) is critical and how
high on it the role must sit. It is subject to the existing prompt-only rule (see
*Deterministic gathering; Inspector is prompt-only*) — this requirement adds only
what is specific to the intelligence Inspector.

Each task-describing text unit SHALL be assessed in its own Inspector call:
profile `SOUL.md`, `AGENTS.md` and `allowed_tools` for `agent_profile`/`service`;
the job prompt for `cron_job` (carried into the inventory); the per-slot capability
already derived for `auxiliary` consumers (see *Auxiliary model slots are
consumers*). A consumer with no describing text SHALL NOT be assessed.

Each call SHALL return a capability axis, an ordinal tier, and a confidence — not a
model and not a raw AA index value, so it does not violate the demand Inspector's
"no model choice" limit: deterministic code maps the tier to an anchor value and
sets the role's quality **anchor** and `minimum_quality_metric` (= the axis). The
band `minimum`/`maximum` SHALL remain derived from demand and capacity by the
existing band computation, not dictated by the Inspector.

#### Scenario: Each describing unit is assessed individually
- GIVEN a role used by one agent profile and one cron job
- WHEN the role's intelligence is assessed
- THEN the profile `SOUL.md`/`AGENTS.md` and the cron job's prompt are each sent in
  their own Inspector call

#### Scenario: Axis and anchor set the band centre, not its edges
- GIVEN the Inspector returns axis `intelligence_index` at a high tier for a role
- WHEN the role's quality band is computed
- THEN the role's `minimum_quality_metric` is `intelligence_index` and the band is
  anchored at the mapped high-tier value
- AND the band `minimum`/`maximum` are still widened from demand and capacity

### Requirement: Role anchor aggregates unit verdicts by maximum

When several describing units route to one role, the role's quality anchor SHALL
be the maximum of its units' assessed needs, and the axis SHALL come from the most
demanding unit, so a shared combo serves its most demanding consumer. Per-unit
verdicts SHALL be aggregated and then passed into the forecast.

#### Scenario: Shared combo takes the most demanding unit
- GIVEN a reasoning-heavy agent and a mechanical cron job share one role
- WHEN the role anchor is aggregated
- THEN the role anchor equals the reasoning-heavy agent's assessed level

### Requirement: Description-less roles take the adequacy floor

A role whose consumers carry no task-describing text SHALL receive the global
`adequacy_floor` as its anchor without an Inspector call, so every role obtains a
band.

#### Scenario: Bare webhook role floors without an LLM call
- GIVEN a role used only by a webhook with no description
- WHEN its quality anchor is resolved
- THEN it is set to the adequacy floor and no intelligence Inspector call is made

### Requirement: Per-unit content-hash cache

The system SHALL store a content hash per describing unit and SHALL re-assess a
unit only when its hash changes; an unchanged unit SHALL reuse its cached verdict
and never be re-sent to the Inspector. A role's anchor SHALL be re-aggregated only
when one of its units' verdicts changes. This is separate from the demand
forecast's consumer-diff refresh (Change-driven forecast refresh): a consumer-set
or schedule diff that refreshes demand SHALL NOT by itself re-run the intelligence
Inspector.

#### Scenario: Unchanged unit reuses its cached verdict
- GIVEN a profile's `SOUL.md`/`AGENTS.md` are unchanged since the last assessment
- WHEN the inventory is processed
- THEN no Inspector call is made for that unit and its cached verdict is reused

#### Scenario: Cadence change does not re-run the intelligence Inspector
- GIVEN only a cron job's schedule changed since the last inventory
- WHEN the inventory diff is processed
- THEN the demand forecast refreshes but the role's quality anchor is not recomputed

#### Scenario: Changed persona re-assesses only its unit
- GIVEN a profile's `SOUL.md` changed since the last inventory
- WHEN the inventory diff is processed
- THEN that unit is re-assessed and the role's anchor is re-aggregated

### Requirement: Default combo grid with snap-to-nearest

The system SHALL bootstrap a grid of reusable default combos over the registered
text/chat pool. A grid cell is itself a **combo** (a ranked member list) keyed by
the full requirement profile `(axis, tier, required_capabilities, context_class)`,
not by `axis × tier` alone — capability and context window are **dimensions of the
cell**, not post-filters on a generic cell, so a cell is always a real populated
combo for its whole profile (e.g. vision + large-context + high-intelligence).

The grid SHALL be **demand-driven**: the system builds one reusable combo per
distinct profile tuple that real roles and auxiliary functions actually exhibit,
NOT the full cartesian product. **Every role SHALL be filled from the grid**, with
no hand-maintained combos: a main role snaps to the cell-combo for its profile
(axis/tier from the Inspector); an auxiliary role snaps to the cheapest combo for
its profile without an Inspector call. Capability (`issubset`) and context window
(`effective_context_window ≥ minimum`) SHALL be applied as hard filters before the
tier orders members. A unique combo SHALL be created only for a tuple seen once.

#### Scenario: Main role snaps to a reusable grid combo
- GIVEN a default combo grid exists and a main role resolves to a grid cell
- WHEN the role's combo is selected
- THEN the role reuses that grid combo and no new combo is created

#### Scenario: Auxiliary role snaps to a cheap capability-matched combo
- GIVEN an auxiliary role with a required capability (e.g. vision for image work,
  tool-calling for mcp/skills, structured output for approval)
- WHEN its combo is filled
- THEN it snaps to the auxiliary combo built from the cheapest models that satisfy
  that capability, and no intelligence Inspector call is made for it
- AND a vision auxiliary never receives a cheaper non-vision combo

#### Scenario: Context window is part of the cell profile
- GIVEN a role whose forecast input tokens require a large context window
- WHEN its combo is selected
- THEN it snaps to a cell-combo whose members all satisfy that context window
- AND it does not reuse a smaller-context cell of the same axis and tier

#### Scenario: Grid is demand-driven, not cartesian
- GIVEN the real roles exhibit only a handful of distinct profile tuples
- WHEN the grid is bootstrapped
- THEN one reusable combo is built per occurring tuple, not for every theoretical
  `(axis, tier, capability, context)` combination

#### Scenario: Singleton profile mints a unique combo
- GIVEN a role whose profile tuple is exhibited by no other role
- WHEN the role's combo is selected
- THEN a unique combo is created for that tuple

### Requirement: Grid is bootstrapped once, then evolves incrementally

The default grid SHALL be set up once at initial deployment, with each default
combo created from a **single seed model** that sets the cell's initial anchor;
bootstrap SHALL NOT pre-fill full member lists. The grid SHALL NOT be
re-bootstrapped wholesale thereafter. After setup the grid SHALL evolve only by
agent-driven rebalance of existing cells (the agents on a combo drive band widening
around the seed anchor and member re-ranking) and by minting a unique per-agent
combo on demand when a new agent's profile tuple is covered by no existing cell.

#### Scenario: Bootstrap seeds one model, agents grow the combo
- GIVEN a default combo is bootstrapped with a single seed model
- WHEN the agents that route to it are forecast
- THEN the band widens around the seed anchor to meet their demand and members
  re-rank, growing the combo from the one seed
- AND this growth happens through rebalance, not at bootstrap

#### Scenario: New agent with a novel profile mints a unique combo
- GIVEN the grid is already set up and a new agent appears whose profile tuple no
  existing cell covers
- WHEN its combo is resolved
- THEN a unique combo is minted on demand (single seed, then agent-rebalanced) and
  joins the rebalancing population
- AND the grid is not re-bootstrapped

### Requirement: Anchor is stable across combo rebalances

The intelligence grid SHALL own only the target (the profile tuple and the quality
anchor), while the existing rebalance machinery (priority reorder by score, quota
recalibration, reactive triggers, drift-guarded apply) owns live membership and
ordering. The anchor SHALL be recomputed only on a persona or description hash
change, and SHALL NOT change on a quota recalibration or priority reorder, so the
band centre does not move under the rebalancer.

#### Scenario: Quota recalibration reorders without re-anchoring
- GIVEN a cell whose members are reordered as quota depletes
- WHEN the rebalance runs
- THEN the cell's anchor is unchanged and only member ordering/membership shifts

#### Scenario: Thin-corner shortfall degrades rather than re-anchors
- GIVEN a high-intelligence (or 1M-context, or vision) cell whose capacity falls
  below its protected demand
- WHEN the band is recomputed
- THEN the band is flagged `degraded` and the anchor is not silently lowered

### Requirement: Intelligence Inspector is advisory

If the intelligence Inspector is unavailable, the system SHALL fall back to the
existing seed-derived anchor and SHALL NOT block the demand forecast.

#### Scenario: Inspector failure falls back to seed anchor
- GIVEN the intelligence Inspector call fails
- WHEN the role's quality anchor is resolved
- THEN the seed-derived anchor is used and the demand forecast still completes
