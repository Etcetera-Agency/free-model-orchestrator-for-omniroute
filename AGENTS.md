<!-- OPENSPEC:START -->
# OpenSpec Instructions

For AI assistants in this project.

Open `@/openspec/AGENTS.md` when request:
- Mentions proposal/spec/change/plan
- Adds capability, breaking change, architecture shift, big perf/security work
- Is ambiguous and needs authoritative spec before code

Use `@/openspec/AGENTS.md` for:
- Proposal create/apply flow
- Spec format/conventions
- Project structure/guidelines

Run OpenSpec CLI as `npx --yes @fission-ai/openspec@latest ...`.

Keep managed block so `openspec update` can refresh it.

<!-- OPENSPEC:END -->

## Executable scenarios (project rule)

Scenarios executable. `tests/test_spec_coverage.py` enforces binding in normal
`pytest`.

When adding/changing tests:

- Bind each test to the scenario it encodes with
  `@pytest.mark.spec("<capability>::<Scenario name>")`. The id is
  `<spec dir name>::<text after "#### Scenario:">` from
  `openspec/specs/**` or an active (non-archived) `openspec/changes/**`.
- After bind, remove covered scenario from `tests/spec_coverage_pending.txt`.
  Pending entries are allowed only for explicitly queued active slices that are
  also listed in `openspec/TODO.md`.

Gate fails when scenario has no test and is not pending, marker points at missing
scenario, or pending entry stale/already covered. See `README.md` ->
"Executable-spec coverage gate".
