# Change: Decompose the composition root into per-domain stage modules

## Why

`src/fmo/composition.py` is 1620 lines — roughly a quarter of all of `src/fmo`.
It carries every one of the 16 stage adapters, the CLI dispatcher, the AA-index
subcommand handlers, smoke testing, current-combo reads, and hash helpers in one
file. This is the single point where everything converges: the highest-churn,
highest-risk module, where unrelated stages share a namespace and a stage change
can ripple into others. It works (tests pass), but it resists isolated reasoning
and review and concentrates regression risk. This is a structural refactor only —
no behavior, exit codes, or persisted shapes change.

## What Changes

- Split `composition.py` into focused modules along existing seams: stage
  adapters grouped by domain (discovery/matching, access/quota, probe/telemetry,
  scoring/allocation/diff, apply/audit), the CLI dispatcher, and the AA-index
  handlers, with a thin composition root that only wires them.
- Public composition entrypoints and their behavior SHALL be preserved exactly;
  the change is import-structure only.
- The full pytest suite (including the executable-spec coverage gate) SHALL pass
  unchanged, proving behavior is identical.

## Impact

- Affected specs: `system-architecture` (ADDED: composition root is decomposed).
- Affected code: `src/fmo/composition.py` split into new modules under
  `src/fmo/`; imports updated; no change to `pipeline.py` stage contracts.
- No schema, CLI, or behavior change. Pure refactor.
