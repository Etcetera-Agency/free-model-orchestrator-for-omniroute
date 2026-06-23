## 1. Establish the package and the import-stability oracle

- [ ] 1.1 Write failing test: importing every public name
      (`Database`, `Repository`, and each `*Repository`) from `fmo.persistence`
      succeeds and the names resolve to classes, bound to
      `system-architecture::Persistence public API stays import-stable`.
- [ ] 1.2 Write failing test: `src/fmo/persistence/` is a package, no single
      aggregate module exceeds a size budget (≈250 lines), and `_base.py` owns
      the shared `Database`/`Repository`/row helpers, bound to
      `system-architecture::Persistence layer is split into per-aggregate modules`.

## 2. Extract the shared base

- [ ] 2.1 Create `src/fmo/persistence/_base.py` with `Database`, `Repository`,
      `_one`, `_optional`, `_many`, `_jsonb`, `_canonical_json`, `_content_hash`,
      `_split_model_id`, `_free_type`, `_trigger_type`.
- [ ] 2.2 Create `src/fmo/persistence/__init__.py` re-exporting the full public
      surface; delete the monolithic `persistence.py` only after the package is
      in place.

## 3. Extract one module per aggregate

- [ ] 3.1 Move each repository class to its own module (`run.py`, `lock.py`,
      `provider.py`, `account.py`, `catalog.py`, `registry.py`,
      `canonical_model.py`, `endpoint.py`, `snapshot.py`, `quota_rule.py`,
      `probe.py`, `role.py`, `role_consumer.py`, `score.py`,
      `allocation_plan.py`, `combo_snapshot.py`, `audit.py`,
      `external_metadata.py`), importing helpers from `._base`.
- [ ] 3.2 Fix the pyright `Unknown | None` row-read errors in the moved modules
      (explicit narrowing / typed row access) so `make typecheck` does not
      regress for the persistence package.

## 4. Close out

- [ ] 4.1 `make check` clean (ruff, format, pyright, vulture).
- [ ] 4.2 Run `tests/test_persistence.py` then the full suite; the suite passes
      unchanged as the behavior oracle.
- [ ] 4.3 Remove the two bound scenarios from `tests/spec_coverage_pending.txt`
      and `EXPECTED_ACTIVE_PENDING` in `tests/test_runtime_documentation.py`.
- [ ] 4.4 `openspec validate refactor-split-persistence --strict`.
