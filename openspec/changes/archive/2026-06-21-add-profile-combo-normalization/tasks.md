# Implementation Tasks (TDD)

Write each test first (red) → green → refactor. PostgreSQL is real. OmniRoute
combo set + canonical mapping from recorded real shapes. Config writes go to a
temp Hermes home in tests.

## Tasks

- [x] 1. TEST: a raw slot `vision: google/gemini-2.5-flash` is rewritten to the
  existing combo whose members include canonical `gemini-2.5-flash` (provider
  ignored) → implement canonical match + target resolution.
- [x] 2. TEST: a slot pointing at a non-existent combo id is rewritten the same
  way (via canonical), and when no combo contains that canonical model it is
  rewritten to the `default` profile's main combo → implement default fallback.
- [x] 3. TEST: a slot already on an existing `fmo-` combo, or on `auto`/empty, is
  left unchanged → implement the keep path.
- [x] 4. TEST: `--dry-run` reports the planned rewrites and writes nothing (no
  file changes, no backups) → implement dry-run.
- [x] 5. TEST: on apply, each touched `config.yaml` is backed up before an atomic
  rewrite, and the rewritten slot routes to the resolved combo with surrounding
  config preserved → implement backup + temp-file/atomic-replace writer.
- [x] 6. TEST: `normalize-profiles` is in the CLI surface and dispatches to the
  normalizer, returning a real outcome/exit code → wire `cli.py`.
- [x] 7. Bind tests with `@pytest.mark.spec("...")`, drop matching lines from
  `tests/spec_coverage_pending.txt`, run full `pytest` and
  `openspec validate add-profile-combo-normalization --strict`.
