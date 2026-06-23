# hermes-inventory Specification (delta)

## ADDED Requirements

### Requirement: Per-role intelligence Inspector

The system SHALL run a second, advisory Inspector — distinct from the demand
Inspector — that estimates the **quality anchor** for each role: which AA axis
(`intelligence_index`, `coding_index`, or `agentic_index`) is critical and how
high on it the role must sit. As with the demand Inspector it is prompt-only:
deterministic code assembles each prompt and the Inspector SHALL NOT read Hermes
files or detect changes.

Each task-describing text unit SHALL be assessed in its own Inspector call:
profile `SOUL.md`, `AGENTS.md` and `allowed_tools` for `agent_profile`/`service`;
the job prompt for `cron_job` (carried into the inventory); the slot's declared
purpose for `auxiliary`. A consumer with no describing text SHALL NOT be assessed.

Each call SHALL return a capability axis, an ordinal tier, and a confidence — not
a raw AA index value. Deterministic code SHALL map the tier to an anchor value and
set the role's quality **anchor** and `minimum_quality_metric` (= the axis); the
band `minimum`/`maximum` SHALL remain derived from demand and capacity by the
existing band computation, not dictated by the Inspector.

#### Scenario: Each describing unit is assessed individually
- GIVEN a role used by one agent profile and one cron job
- WHEN the role's intelligence is assessed
- THEN the profile `SOUL.md`/`AGENTS.md` and the cron job's prompt are each sent in
  their own Inspector call
- AND each Inspector call receives one assembled prompt and reads no files itself

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
when one of its units' verdicts changes, not on every consumer-set diff.

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

The system SHALL bootstrap a grid of reusable default combos spanning the AA
range of the registered text/chat pool (by axis and tier, plus a cheap auxiliary
cell). **Every combo SHALL be filled from the grid**, with no hand-maintained
combos: a main role snaps to the cell for its resolved axis and anchor; an
auxiliary combo snaps to the cheap auxiliary (low) cell without an Inspector call.
A unique combo SHALL be created only when a role fits no cell.

#### Scenario: Main role snaps to a reusable grid combo
- GIVEN a default combo grid exists and a main role resolves to a grid cell
- WHEN the role's combo is selected
- THEN the role reuses that grid combo and no new combo is created

#### Scenario: Auxiliary combo snaps to the cheap cell without assessment
- GIVEN an auxiliary combo (e.g. title-generation, compression, vision)
- WHEN its combo is filled
- THEN it snaps to the cheap auxiliary grid cell and no intelligence Inspector call
  is made for it

#### Scenario: Special role mints a unique combo
- GIVEN a role whose resolved axis and anchor match no grid cell
- WHEN the role's combo is selected
- THEN a unique combo is created for that role

### Requirement: Intelligence Inspector is advisory

If the intelligence Inspector is unavailable, the system SHALL fall back to the
existing seed-derived anchor and SHALL NOT block the demand forecast.

#### Scenario: Inspector failure falls back to seed anchor
- GIVEN the intelligence Inspector call fails
- WHEN the role's quality anchor is resolved
- THEN the seed-derived anchor is used and the demand forecast still completes
