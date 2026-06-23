# Change: Split persistence.py into a per-aggregate repository package

## Why

`src/fmo/persistence.py` is 1240 lines holding 16 repository classes plus the
`Database`/`Repository` base and the `_one/_optional/_many/_jsonb/_content_hash`
row helpers. Every stage imports from this one module, so unrelated aggregates
(runs, providers, quota, audit, external metadata) churn the same file and the
blast radius of any edit is the whole persistence layer. This is the smallest
god-module and the natural place to prove the package-with-re-export-shim pattern
the larger `composition_stages.py` split will reuse.

The `persistence` capability already requires "table SQL exists only in
repository classes" and one typed function per domain table — this change keeps
that behavior and only sharpens the **physical layout** into one module per
aggregate over a shared base, so the boundary is enforced by structure, not
convention.

## What Changes

- Convert `src/fmo/persistence.py` into a `src/fmo/persistence/` package:
  - `_base.py` — `Database`, `Repository`, and the module-private row helpers
    (`_one`, `_optional`, `_many`, `_jsonb`, `_canonical_json`, `_content_hash`,
    `_split_model_id`, `_free_type`, `_trigger_type`).
  - one module per aggregate: `run.py`, `lock.py`, `provider.py`, `account.py`,
    `catalog.py`, `registry.py`, `canonical_model.py`, `endpoint.py`,
    `snapshot.py`, `quota_rule.py`, `probe.py`, `role.py`, `role_consumer.py`,
    `score.py`, `allocation_plan.py`, `combo_snapshot.py`, `audit.py`,
    `external_metadata.py`.
- `persistence/__init__.py` re-exports every public name (`Database`,
  `Repository`, all `*Repository` classes) so existing `from fmo.persistence
  import ...` call sites keep working unchanged — the **shim** that makes the
  split behavior-preserving.
- Fix the pyright errors that live in the moved code as each module is extracted
  (narrow `Unknown | None` row reads), so `make typecheck` does not regress.

## Impact

- Affected specs: `system-architecture` (ADDED structural requirement)
- Affected code: `src/fmo/persistence.py` → `src/fmo/persistence/` package; no
  change to importers. Behavior-preservation oracle: the existing pytest suite
  (notably `tests/test_persistence.py`) passes unchanged.
- Pattern reused by: `refactor-split-stages-*`, `refactor-unify-shared-helpers`.
