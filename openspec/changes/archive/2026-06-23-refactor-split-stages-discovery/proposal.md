# Change: Split the discovery/quota/access stages out of composition_stages.py

## Why

`src/fmo/composition_stages.py` is 2239 lines holding every pipeline stage plus
its private helpers in one module. The existing `system-architecture` requirement
"Composition root stays within a single-responsibility boundary" already wants
stage adapters "grouped by domain in dedicated modules", but today they all live
in this one file. This is the first of three slices that turn
`composition_stages.py` into a `composition_stages/` package, one cluster at a
time, each behind a re-export shim so the wiring in `composition.py` and the
production adapter table keep working unchanged.

This slice extracts the **front of the pipeline**: metadata, free-candidate and
account discovery, model matching, quota research/sync, and access
classification — the stages that turn raw OmniRoute/catalog data into classified,
quota-annotated endpoints.

## What Changes

- Begin the `src/fmo/composition_stages/` package with a `__init__.py` shim that
  re-exports the full public surface used by `composition.py` and
  `_production_stage_adapters()`.
- Extract these stages and their private helpers into focused modules:
  - `discovery.py` — `_metadata_stage`, `_free_candidate_stage`,
    `_account_discovery_stage`, `_persist_account_discovery`,
    `_previous_account_pools`, `_scan_catalogs`, `_model_matching_stage`.
  - `quota.py` — `_quota_research_stage`, `_quota_research_skipped_result`,
    `_quota_sync_stage`, `_quota_limit_hints`, `_quota_hint_key`,
    `_detect_free_model_changes`, `_free_models_from_registry_snapshot`,
    `_reachable_providers`, `_deactivate_lost_free_models`,
    `_ensure_quota_pool`, `_ensure_named_quota_pool`.
  - `access.py` — `_access_classification_stage`,
    `_record_lost_free_access_state`, `_canonical_access_status`,
    `_capacity_weight`.
- Shared cross-cluster helpers (`_effect_result`, `_canonical_slug`,
  `_hash_parts`, `_quota_metric`, …) stay in `composition_stages.py` for now and
  move to a dedicated helpers module in `refactor-split-stages-apply`; the
  remaining stages keep importing them unchanged this slice.
- Fix the pyright errors in the moved modules as they are extracted.

## Impact

- Affected specs: `system-architecture` (ADDED structural requirement)
- Affected code: `src/fmo/composition_stages.py` (stages removed), new
  `src/fmo/composition_stages/{__init__,discovery,quota,access}.py`. No change to
  `composition.py` wiring or the adapter table. Oracle: existing pytest suite
  (`tests/test_composition.py`, `tests/test_discovery.py`, `tests/test_quota.py`)
  passes unchanged.
- Follows the shim pattern proven in `refactor-split-persistence`.
