## 1. Oracles

- [x] 1.1 Write failing test: `_account_discovery_stage`, `_model_matching_stage`,
      `_quota_research_stage`, `_quota_sync_stage`, and
      `_access_classification_stage` resolve via `inspect.getmodule(...)` to
      `fmo.composition_stages.{discovery,quota,access}` and **not** to
      `fmo.composition_stages._legacy`, bound to
      `system-architecture::Discovery, quota, and access stages live in dedicated
      modules`. (Extend the existing structural assertions in
      `tests/test_runtime_documentation.py`.)

## 2. Drain discovery

- [x] 2.1 Move `_account_discovery_stage`, `_free_candidate_stage`,
      `_metadata_stage`, `_model_matching_stage`, `_scan_catalogs` and their
      private helpers (`_detect_free_model_changes`,
      `_free_models_from_registry_snapshot`, `_persist_account_discovery`,
      `_previous_account_pools`, `_reachable_providers`) into `discovery.py`;
      delete the matching `_legacy` wrappers.

## 3. Drain quota

- [x] 3.1 Move `_quota_research_stage`, `_quota_sync_stage`, `_ensure_quota_pool`,
      `_ensure_named_quota_pool`, `_quota_hint_key`, `_quota_limit_hints`,
      `_quota_research_skipped_result` into `quota.py`; delete the matching
      `_legacy` wrappers.

## 4. Drain access

- [x] 4.1 Move `_access_classification_stage`, `_canonical_access_status`,
      `_record_lost_free_access_state`, `_deactivate_lost_free_models` into
      `access.py`; delete the matching `_legacy` wrappers.

## 5. Rewire and close out

- [x] 5.1 Repoint moved bodies at canonical helpers (`fmo.idempotency`,
      `fmo.quota_normalize`, `_helpers`) instead of `_legacy.*` aliases; update
      the `__init__` adapter map to reference the now-local definitions.
- [x] 5.2 `make check` clean (resolve the pyright errors surfaced by the move).
- [x] 5.3 Run the focused discovery/quota/access composition + spec docs tests;
      defer the full suite to the terminal `refactor-drain-stages-apply` slice.
- [x] 5.4 `git diff --check`; `openspec validate refactor-drain-stages-discovery --strict`.
