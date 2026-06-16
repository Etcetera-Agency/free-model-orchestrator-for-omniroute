# Implementation Tasks (TDD)

Write each test first (red) → green → refactor. Mock only the network boundary
with **recorded real** responses (project.md → Testing Strategy). PostgreSQL is
**real**. Hermes shapes: `NousResearch/hermes-agent` (`cron/jobs.py`, profiles,
`hermes webhook subscribe`, services).

## Fixtures to record (real)

- Real `~/.hermes/cron/jobs.json` sample.
- Real agent profile dir (`openclaw.config.yaml` + schemas) and a webhook
  subscription + a service definition.
- Recorded Instructor forecast completion (valid + one with missing fields).

## Tasks

- [ ] 1. TEST: each adapter (filesystem/command/http) normalizes its real sample to one internal schema; missing required env fails startup → implement adapters.
- [ ] 2. TEST: daily inventory records all consumer types (`agent_profile`, `cron_job`, `webhook`, `service`) with cadence + calls_per_run → implement inventory.
- [ ] 3. TEST: an unknown role triggers an immediate FULL inventory (not partial) → implement unknown-role trigger.
- [ ] 4. TEST: inventory diff on consumer/frequency change marks forecast stale → Inspector → allocation; rebuild only if allocation changed materially → implement diff-driven refresh.
- [ ] 5. TEST: deterministic code gathers consumers + computes the diff + assembles the prompt; the Inspector is handed one prompt and does NOT read files or diff state → implement gathering/prompt assembly.
- [ ] 6. TEST: Inspector (Instructor) returns forecast only (no model choice, no quota change); no secrets in the prompt → implement Inspector call.
- [ ] 7. TEST: reconciliation marks a once-missing role retiring (not deleted); deletes only after grace + zero observed use → implement lifecycle.
- [ ] 8. TEST: removed role → inactive + missing_since, combo kept during grace; reappearance reactivates → implement removed/reactivate.
- [ ] 9. TEST: brand-new role gets a template policy + cold-start demand before allocation → implement new-role bootstrap.
