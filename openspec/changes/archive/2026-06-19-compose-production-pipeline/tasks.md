## 1. Composition root

- [x] 1.1 Failing test: the production dispatch path (no injected `pipeline_runner`) executes a per-stage command through a real `PipelineRunner`, not an unconditional success
- [x] 1.2 Implement `src/fmo/composition.py` building Repository, OmniRouteClient, the canonical ordered `Stage` list, the `PipelineRunner`, and a repository-backed diagnostics reader from validated startup config
- [x] 1.3 Failing test: the canonical stage list matches `pipeline.CANONICAL_STAGE_NAMES` in order
- [x] 1.4 Implement the ordered stage registry binding the existing stage modules (no stage logic reimplemented here)

## 2. Wire production defaults

- [x] 2.1 Failing test: `explain-endpoint` / `explain-role` return non-null persisted output on the production path (no injected `diagnostics_reader`)
- [x] 2.2 Implement `_dispatch_cli` / `bootstrap_and_dispatch` to pass the composed runner and diagnostics reader as defaults
- [x] 2.3 Failing test: per-stage command exit code reflects a stage failure surfaced by the real runner

## 3. Validation

- [x] 3.1 Run targeted pytest for `tests/test_cli.py` and `tests/test_bootstrap.py`
- [x] 3.2 Run full `pytest -q`
- [x] 3.3 `openspec validate compose-production-pipeline --strict`
