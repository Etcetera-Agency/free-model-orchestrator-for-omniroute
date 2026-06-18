# Change: Wire CLI commands to the pipeline runner

## Why

`cli.py`'s `run_cli` only invokes real work for `sync-metadata`/`full`; every
other command (`scan-providers`, `match-models`, `probe-models`, `allocate`,
`diff`, `apply`, `rollback`, `explain-*`, `aa-index ...`) returns
`CliResult(success)` without doing anything, and `apply` merely flips a
`changed` flag with none of the safety gating the spec promises. The documented
operator command surface is non-functional. This slice makes each command invoke
its corresponding pipeline stage through the runner.

## What Changes

- **BREAKING** behavior change: per-stage commands now execute the matching
  pipeline stage via the runner and return that stage's real outcome and exit
  code, instead of an unconditional success.
- `apply` runs through the runner's fail-closed gating (DB availability,
  snapshot, valid desired state, quota safety, probe) and returns 5/6/7 on the
  corresponding failures.
- `explain-endpoint` / `explain-role` read persisted state and print real score
  components / selection rationale.
- Keep `--dry-run` local-only (no `/api/combos/test`) and key redaction.

## Impact

- Affected specs: `cli-and-operations` (MODIFIED operator command set).
- Affected code: `src/fmo/cli.py` `run_cli`; consumes the pipeline runner and
  repository layer.
- Depends on `add-pipeline-orchestration` (and transitively `persistence`).
