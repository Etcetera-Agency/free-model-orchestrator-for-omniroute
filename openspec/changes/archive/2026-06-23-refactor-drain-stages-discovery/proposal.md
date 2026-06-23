# Change: Drain the discovery/quota/access stage bodies out of `_legacy.py`

## Why

The `refactor-split-stages-*` slices created the per-domain module layout but the
stage **bodies never moved**: `discovery.py`, `quota.py`, and `access.py` are
one-line delegations (`return _legacy._xxx(...)`) and the implementations still
live in the 2255-line `composition_stages/_legacy.py` monolith. Navigating to a
front-of-pipeline stage still lands in `_legacy`, so "stage domains live in
separate modules" holds only in letter, not intent.

This is the first of three drain slices (front → middle → back), mirroring the
original split sequence. It moves the front-of-pipeline bodies into the modules
that already front them; `_legacy.py` shrinks but is not yet deleted (the
terminal `refactor-drain-stages-apply` slice deletes it after all clusters are
drained).

## What Changes

- **Move into `discovery.py`** (deleting the matching `_legacy` wrappers, so each
  function is *defined* here): `_account_discovery_stage`, `_free_candidate_stage`,
  `_metadata_stage`, `_model_matching_stage`, `_scan_catalogs`, and their private
  helpers `_detect_free_model_changes`, `_free_models_from_registry_snapshot`,
  `_persist_account_discovery`, `_previous_account_pools`, `_reachable_providers`.
- **Move into `quota.py`**: `_quota_research_stage`, `_quota_sync_stage`,
  `_ensure_quota_pool`, `_ensure_named_quota_pool`, `_quota_hint_key`,
  `_quota_limit_hints`, `_quota_research_skipped_result`.
- **Move into `access.py`**: `_access_classification_stage`,
  `_canonical_access_status`, `_record_lost_free_access_state`,
  `_deactivate_lost_free_models`.
- Point each moved body at the canonical cross-cluster helpers directly
  (`fmo.idempotency`, `fmo.quota_normalize`, `_helpers`) instead of routing
  through a `_legacy.*` alias.
- Update the `__init__` adapter map so the front-of-pipeline adapters reference
  the now-local definitions; the base `_production_stage_adapters` in `_legacy`
  keeps building the rest until the terminal slice.
- Fix the pyright errors that surface once the front-of-pipeline wrappers are
  gone.

## Impact

- **Affected specs:** `system-architecture` — MODIFY "Discovery, quota, and access
  stages are dedicated modules" from "a module exists" to "the module *defines*
  the stage" (no delegation to `_legacy`).
- **Affected code:** front-of-pipeline bodies leave `_legacy.py` for
  `discovery.py` / `quota.py` / `access.py`; `_legacy.py` stays (shrunk).
- **External surface unchanged:** the `__init__` shim re-exports each symbol from
  its domain module; `fmo.composition` and `tests/_composition_support` keep
  working.
- **Behavior-preservation oracle:** focused discovery/quota/access composition
  tests + `tests/test_runtime_documentation.py` pass unchanged; the full suite is
  deferred to the terminal slice per the staged-refactor convention.
- **Depends on** the archived `refactor-split-stages-discovery`.
