# hermes-inventory Specification (delta)

## ADDED Requirements

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
