# Implementation Tasks (TDD)

Write each test first (red) → green → refactor. Mock only the source boundary
with **recorded real** Hermes shapes (`v2026.6.19`). PostgreSQL is real.
Hermes shapes: `NousResearch/hermes-agent@v2026.6.19` (`hermes_cli/profiles.py`,
`website/docs/user-guide/configuring-models.md`, `cli-config.yaml.example`).

## Fixtures to record (real)

- `config.default.yaml` — main `model:` mapping → combo id, no `auxiliary`.
- `config.research.yaml` — main mapping + `auxiliary:` with one explicit
  override and one `auto` slot.
- `config.fresh.yaml` — `model: ""` sentinel.

## Tasks

- [x] 1. TEST: the profile reader joins `ProfileInfo.path` + `config.yaml` and
  returns `main_combo` from `model.default` (mapping) for `config.default.yaml`
  → implement per-profile config read.
- [x] 2. TEST: a profile with `auxiliary:` (`config.research.yaml`) exposes the
  raw `auxiliary` mapping unchanged (both the override and the `auto` slot are
  present) → carry the block through the reader.
- [x] 3. TEST: `model: ""` (`config.fresh.yaml`) yields `main_combo = None`
  without raising → handle the empty-string sentinel and legacy bare-string form.
- [x] 4. TEST: `parse_profiles` emits the same single main consumer as before
  but sourced from `config.yaml` `main_combo`, not the list summary `model`
  → switch the source while keeping consumer-type selection (gateway_running).
- [x] 5. Bump the documented Hermes pin `v2026.6.5 → v2026.6.19`
  (`ORACLE_FRESH_SERVER_DEPLOY.md`, `tests/test_hermes_inventory_real_shapes.py`
  header) and confirm the other recorded shapes still parse.
- [x] 6. Bind tests with `@pytest.mark.spec("...")`, drop matching lines from
  `tests/spec_coverage_pending.txt`, run full `pytest` and
  `openspec validate update-hermes-source-to-per-profile-config --strict`.
