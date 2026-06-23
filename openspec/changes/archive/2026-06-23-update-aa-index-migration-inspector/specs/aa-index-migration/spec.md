## MODIFIED Requirements

### Requirement: LLM proposal via strongest model

The system SHALL select the highest available new-`intelligence_index`
confirmed-free model through the shared Instructor runtime resolver and use an
Instructor `MigrationProposal` to propose new per-role thresholds. The migration
agent SHALL load the external `aa-index-migration` prompt file through the
shared prompt assembly path and SHALL receive deterministic, non-secret context
for the old index version, new index version, old/new metric distributions,
active role policies, current combos, capacity summaries, and percentile
mappings. Percentile mapping SHALL be a reference signal only, not the mandatory
algorithm. The prompt context SHALL NOT be limited to the selected migration
model JSON.

#### Scenario: Proposal generation
- GIVEN a migration is in progress and the shared runtime resolver can select a capable confirmed-free model
- WHEN the migration agent runs
- THEN it loads the external `aa-index-migration` prompt file
- AND the prompt includes the old/new index versions, distributions, roles, capacity summary, and percentile mapping
- AND it returns a structured threshold proposal

#### Scenario: Prompt is not selected-model JSON
- GIVEN `aa-index analyze` runs for a new AA index version
- WHEN the migration Instructor call is prepared
- THEN the prompt is assembled from the migration prompt file and migration context
- AND the prompt is not merely the selected model record serialized as JSON

### Requirement: Deterministic validation, approval and rollback

The system SHALL validate the proposal deterministically before persistence and
again before rollout. Validation SHALL include schema, index version, known
role, allowed metric, threshold presence in the new scale, free confirmed
endpoint eligibility, minimum combo size, independent quota pools, provider
diversity, protected demand, required capabilities, minimum context, endpoint
health, quality gate, and live quota capacity. Validation failure SHALL NOT
mutate production thresholds or combos. The system SHALL run a bounded
operational repair loop by returning validation error codes to the same
migration agent for at most three attempts; unrepaired invalid advice SHALL end
in manual review or a fail-closed command result. Approved rollout SHALL run a
dry-run and revalidate against stored baseline facts plus current repository
state before inserting active threshold versions. It SHALL roll back on smoke
test failure. If no migration model is available, production thresholds and
combos SHALL remain unchanged.

#### Scenario: No migration model
- GIVEN no confirmed-free model with fresh usable quota is available through the shared runtime resolver
- WHEN migration is attempted
- THEN no Instructor request is sent to a paid or unconfirmed model
- AND production thresholds and combos remain unchanged

#### Scenario: Invalid proposal enters repair loop
- GIVEN the migration agent returns a proposal that fails deterministic validation
- WHEN validation reports repairable errors
- THEN those error codes are sent into the next repair attempt
- AND a valid repaired proposal may be persisted as proposed
- AND no threshold version is changed before operator approval

#### Scenario: Unrepaired proposal fails closed
- GIVEN all allowed repair attempts return invalid proposals
- WHEN the repair limit is reached
- THEN no rollout-ready proposal is persisted
- AND production thresholds and combos remain unchanged
- AND the command reports manual review or deterministic failure

#### Scenario: Rollout revalidates proposal
- GIVEN an operator approved a migration proposal
- WHEN `aa-index rollout` runs
- THEN deterministic validation runs again against the stored baseline and current repository state
- AND threshold versions are inserted only after validation and dry-run pass

#### Scenario: Rollout drift blocks mutation
- GIVEN an approved proposal was valid at analyze time
- AND current quota, health, capability, provider diversity, context, or combo-size state no longer satisfies the proposal
- WHEN `aa-index rollout` runs
- THEN no active threshold version is changed
- AND the migration is not marked `rolled_out`

#### Scenario: Smoke test fails after rollout
- GIVEN approved thresholds are rolled out and the smoke test fails
- WHEN failure is handled
- THEN the migration is rolled back to the previous thresholds

### Requirement: Migration agent runs in production via the shared runtime

The production migration capability SHALL invoke `run_migration_agent` over the
shared Instructor runtime for the `analyze`/`proposal` steps. The migration
site SHALL leave model resolution to the shared runtime resolver and SHALL NOT
perform a duplicate resolver-less model availability check before calling the
runtime. The LLM output is an advisory threshold proposal only; deterministic
code SHALL own freeze on AA version change, context construction, proposal
validation, repair-loop decisions, approval, rollout, and smoke-fail rollback.
When AA fetch fails, no resolver model is available, or proposal validation
fails closed, the capability SHALL keep existing combos and thresholds frozen.

#### Scenario: Advisory proposal generated
- **WHEN** `aa-index analyze` runs with the runtime available
- **THEN** `run_migration_agent` produces an advisory threshold proposal through the shared runtime
- **AND** the proposal is persisted with baseline snapshot facts but not auto-applied

#### Scenario: Deterministic approval and rollout
- **WHEN** an operator approves and rolls out a proposal
- **THEN** thresholds change only through the deterministic rollout path
- **AND** a smoke-test failure after rollout triggers deterministic rollback

#### Scenario: AA unavailable freezes thresholds
- **WHEN** the AA fetch fails or no migration model is available
- **THEN** thresholds and combos stay frozen and the run fails closed

#### Scenario: Shared resolver handles migration model selection
- **GIVEN** `aa-index analyze` runs in production composition
- **WHEN** the migration Instructor site requests a model
- **THEN** the shared runtime resolver performs the fresh live quota check
- **AND** `aa-index` does not run a separate resolver-less pre-check that can disagree with the shared resolver
