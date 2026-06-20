# Change: Compose the production pipeline (default CLI wiring)

## Why

`update-cli-stage-execution` (archived, IMPLEMENTED) reshaped `run_cli` to accept
an injected `pipeline_runner` and `diagnostics_reader`, and its spec states that
per-stage commands SHALL NOT return an unconditional success and that
diagnostics SHALL read persisted state. The production call path, however, is
`main → bootstrap_and_dispatch → _dispatch_cli → run_cli(argv, preconditions_ok=...)`
and passes **neither** dependency. So in production:

- `run_cli` hits `if pipeline_runner is None: return CliResult(success, changed=False)`
  for every per-stage command (`scan-providers`, `match-models`, `probe-models`,
  `score-roles`, `allocate`, `diff`, `apply`, `rollback`, `full`) — a no-op.
- `explain-endpoint` / `explain-role` return `output=None` because
  `diagnostics_reader is None`.

Nothing builds the canonical `Stage` list from the real stage modules in
production: `Stage(` and `PipelineRunner(` appear only in tests. The shipped
runtime contradicts the shipped `cli-and-operations` spec. This slice adds the
missing composition root so the documented command surface actually executes.

## What Changes

- Add a composition root (`src/fmo/composition.py`) that, from validated
  startup config, builds: a `Repository` from `DATABASE_URL`, an
  `OmniRouteClient`, the canonical ordered `Stage` list bound to the existing
  stage modules (discovery, match, quota, probe, telemetry, scoring, allocation,
  applier, audit), a `PipelineRunner`, and a repository-backed diagnostics
  reader.
- `_dispatch_cli` supplies these as the **production defaults** to `run_cli`, so
  per-stage commands execute their stage and return its real outcome/exit code,
  and `explain-*` print real persisted state.
- Keep the injected-seam signatures intact for tests; this slice only changes the
  production defaults from `None` to the composed objects.
- Add a regression test that calls the production dispatch path **without**
  injected seams and asserts a stage actually ran (not unconditional success) and
  that `explain-*` produced non-null output.

## Impact

- Affected specs: `runtime-bootstrap` (ADDED: default production pipeline wiring).
- Affected code: new `src/fmo/composition.py`; `src/fmo/cli.py` `_dispatch_cli`;
  `src/fmo/bootstrap.py` (pass composed objects through dispatch).
- Depends on `add-pipeline-orchestration`, `update-cli-stage-execution`,
  `add-persistence-repositories`.
