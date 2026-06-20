# Implementation Tasks (TDD)

Write each test first (red) → green → refactor. PostgreSQL is **real**. Assert
that no OmniRoute mutation and no `/api/combos/test` call happen on `--dry-run`,
using a recording fake OmniRoute client (`../OmniRoute` shapes).

## Tasks

- [x] 1. TEST: `diff --dry-run` runs the diff stage and returns the stage's real
  outcome (not unconditional success) without mutating OmniRoute → remove the
  blanket dry-run short-circuit in `run_cli`.
- [x] 2. TEST: `apply --dry-run` runs the precondition/validation path and
  reports the would-be outcome (e.g. `unsafe_to_apply` when a gate fails) without
  applying any combo and without calling `/api/combos/test` → honor
  `config["dry_run"]` in the apply stage.
- [x] 3. TEST: `full --dry-run` runs all stages read-only and surfaces the real
  worst-status exit code, writing no OmniRoute mutation → verify end to end.
- [x] 4. TEST: metadata `--dry-run` behavior is unchanged (external fetch
  validated, no DB writes) → regression guard.
- [x] 5. Bind tests with `@pytest.mark.spec("cli-and-operations::...")`, drop
  matching lines from `tests/spec_coverage_pending.txt`, run full `pytest` and
  `openspec validate fix-cli-dry-run-pipeline-preview --strict`.
