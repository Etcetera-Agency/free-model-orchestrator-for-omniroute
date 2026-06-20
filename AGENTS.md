<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

## Executable scenarios (project rule)

Scenarios are executable and the binding is enforced by
`tests/test_spec_coverage.py`, which runs as part of the normal `pytest` suite.

When you add or change tests:

- Bind each test to the scenario it encodes with
  `@pytest.mark.spec("<capability>::<Scenario name>")`. The id is
  `<spec dir name>::<text after "#### Scenario:">` from
  `openspec/specs/**` or an active (non-archived) `openspec/changes/**`.
- After binding, remove the now-covered scenario from
  `tests/spec_coverage_pending.txt`. That allowlist must shrink, never grow.

The gate fails the build when a scenario has no test and is not pending, when a
marker points at a non-existent scenario, or when a pending entry is stale or
already covered. See `README.md` → "Executable-spec coverage gate".