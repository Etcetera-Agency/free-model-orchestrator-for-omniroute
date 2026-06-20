# fix-cli-dry-run-pipeline-preview

## Why

`--dry-run` is a no-op for every pipeline command except metadata sync:

```python
# src/fmo/cli.py:run_cli
if args.dry_run:
    return CliResult(exit_code=EXIT_CODES["success"], changed=False, combo_test_called=False)
```

This early return fires before any stage runs, for `diff`, `allocate`, `apply`,
`full`, etc. So `apply --dry-run`, `diff --dry-run`, and `full --dry-run` return
unconditional success without validating anything. This contradicts the documented
contract — README: "dry-run validates without writes" — and the
`cli-and-operations` "Local dry-run without combo test" requirement, which says
the *final combo* is validated locally on `--dry-run`. It also produces a
misleading green exit code: an operator running `apply --dry-run` to preview a
plan gets `0` regardless of whether the plan is unsafe.

The stages already carry the dry-run flag in `PipelineContext.config["dry_run"]`,
so the unconditional short-circuit is the only thing preventing a real read-only
preview.

## What Changes

- Remove the blanket `if args.dry_run: return success` short-circuit from
  `run_cli`.
- Run the selected stages with `dry_run=True` so each stage performs its
  read-only validation and reports its real outcome/exit code, while making no
  OmniRoute mutation and no `/api/combos/test` call. Mutating stages (`apply`)
  SHALL execute their precondition/validation path and report the would-be
  outcome without mutating combos.
- Keep the existing metadata `--dry-run` behavior (validate external fetches,
  no DB writes).

## Impact

- Modified spec: `cli-and-operations` (Local dry-run without combo test — extend
  to all pipeline commands, not just allocation).
- Affected code: `src/fmo/cli.py::run_cli`, dry-run handling in
  `src/fmo/composition_stages.py` apply/diff stages (honor
  `config["dry_run"]`).
- Risk: `--dry-run` exit codes change from always-0 to the real validated
  outcome; this is the intended fix. Confirm any caller/cron that relied on the
  old always-success behavior.
