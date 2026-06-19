# Implementation Tasks

## 1. TDD Coverage

- [x] 1.1 Add failing tests proving `sync-free-registry` calls the free registry
  domain adapter and persists/records its real outcome.
- [x] 1.2 Add failing tests proving `scan-providers` calls the OmniRoute catalog
  scanner path and writes provider/account/catalog/endpoint state.
- [x] 1.3 Add failing tests proving `full` invokes every canonical stage adapter
  in order and fails if any adapter is replaced by unconditional success.
- [x] 1.4 Add failing tests for stage error translation:
  `partial_stale`, `validation_failed`, `external_dependency_failed`,
  `unsafe_to_apply`, `apply_failed_rolled_back`, `rollback_failed`.

## 2. Production Composition

- [x] 2.1 Add a production stage dependency object for repository, OmniRoute
  client, startup config, and stage collaborators.
- [x] 2.2 Replace `_successful_stage` placeholders with real adapter-backed
  stages for registry sync and provider/catalog discovery.
- [x] 2.3 Replace placeholder quota/access/probe/telemetry/quota-sync/scoring
  stages with adapters around existing modules.
- [x] 2.4 Replace placeholder allocation/diff/apply/audit stages with adapters
  around existing modules and repository-backed preconditions.
- [x] 2.5 Fix `_COMMAND_STAGE_NAMES` so each operator command invokes its exact
  production stage path.
- [x] 2.6 Remove placeholder helper code once no production stage uses it.

## 3. Verification

- [x] 3.1 Run targeted tests for composition, CLI, scheduler, provider scanner,
  registry, pipeline, and apply guard.
- [x] 3.2 Run `.venv/bin/python -m pytest -q`.
- [x] 3.3 Run `npx --yes @fission-ai/openspec@latest validate --all --strict`.
- [x] 3.4 Use Code Simplifier before finishing the implemented slice.
- [x] 3.5 Update `completion.review` with fixes and any newly discovered
  follow-up work.
- [x] 3.6 Update `openspec/TODO.md` before finishing if deferred scope remains.
