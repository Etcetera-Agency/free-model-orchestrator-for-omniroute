## MODIFIED Requirements

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
