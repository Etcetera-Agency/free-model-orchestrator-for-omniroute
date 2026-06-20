# cli-and-operations Specification

## MODIFIED Requirements

### Requirement: Local dry-run without combo test

The system SHALL perform local dry-run validation of the final combo without
upstream model calls and SHALL never call `/api/combos/test`. On `--dry-run` the
CLI SHALL execute the selected pipeline stage(s) in read-only mode rather than
returning an unconditional success: each stage SHALL run its validation path and
report its real outcome and exit code, while making no OmniRoute mutation. The
`apply` command on `--dry-run` SHALL run its precondition/validation path and
report the would-be outcome (including `unsafe_to_apply`) without mutating any
combo.

#### Scenario: Dry-run validation
- GIVEN `--dry-run`
- WHEN allocation completes
- THEN the combo is validated locally and `/api/combos/test` is not called

#### Scenario: Dry-run runs the stage, not an unconditional success
- GIVEN `diff --dry-run` or `full --dry-run`
- WHEN the command runs
- THEN the selected stage(s) execute read-only and the exit code reflects the
  real stage outcome
- AND no OmniRoute mutation call is made

#### Scenario: Apply dry-run previews without mutating
- GIVEN `apply --dry-run` and a failing safety gate
- WHEN the command runs
- THEN the precondition/validation path runs and reports `unsafe_to_apply`
- AND no combo is mutated and `/api/combos/test` is not called
