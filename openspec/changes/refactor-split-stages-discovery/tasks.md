## 1. Start the package and the wiring oracle

- [ ] 1.1 Write failing test: the `_production_stage_adapters()` table and
      `composition.py` resolve the metadata/discovery/quota/access stages
      unchanged after the move, bound to
      `system-architecture::Stage package re-exports preserve composition wiring`.
- [ ] 1.2 Write failing test: discovery, quota, and access stages live in
      dedicated modules under `fmo.composition_stages`, and no extracted module
      defines a stage from a different cluster, bound to
      `system-architecture::Discovery, quota, and access stages live in dedicated modules`.

## 2. Create the package shim

- [ ] 2.1 Create `src/fmo/composition_stages/__init__.py` re-exporting the full
      public surface currently imported from `fmo.composition_stages` (stage
      builders, `StageDependencies`, `StageAdapters`, `_production_stage_adapters`).
- [ ] 2.2 Keep cross-cluster helpers in place so later-cluster stages still
      import them unchanged this slice.

## 3. Extract the discovery, quota, and access clusters

- [ ] 3.1 Move the discovery stage + helpers into `discovery.py`.
- [ ] 3.2 Move the quota research/sync stages + helpers into `quota.py`.
- [ ] 3.3 Move the access-classification stage + helpers into `access.py`.
- [ ] 3.4 Fix the pyright errors in the three moved modules.

## 4. Close out

- [ ] 4.1 `make check` clean.
- [ ] 4.2 Run `tests/test_discovery.py`, `tests/test_quota.py`,
      `tests/test_composition.py`, then the full suite; it passes unchanged.
- [ ] 4.3 Remove the two bound scenarios from `tests/spec_coverage_pending.txt`
      and `EXPECTED_ACTIVE_PENDING`.
- [ ] 4.4 `openspec validate refactor-split-stages-discovery --strict`.
