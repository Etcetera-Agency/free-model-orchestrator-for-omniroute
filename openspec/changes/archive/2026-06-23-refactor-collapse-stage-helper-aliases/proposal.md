# Change: Collapse the `_helpers.py` slug/hash/quota-math re-export aliases

## Why

`refactor-unify-shared-helpers` made `fmo.idempotency` and `fmo.quota_normalize`
the canonical homes for the slug/hash and quota-math helpers, but left a
compatibility shim behind in `composition_stages/_helpers.py`:

```python
_canonical_slug = canonical_slug
_hash_parts = hash_parts
_quota_metric = quota_metric
_quota_limit = quota_limit
_remaining_amount = remaining_amount
```

These five module-level aliases re-export the canonical functions under their old
underscore names, and `__init__.py` re-exports them again from `_helpers`. It is a
purely mechanical indirection layer: nothing outside the package reads
`composition_stages._canonical_slug` (verified — no consumers in `src/` or `tests/`
outside the package itself), and every real call site can import the canonical
name directly. The `_helpers` module should hold only genuine cross-cluster stage
helpers, not a rename table for `idempotency`/`quota_normalize`.

This is a cleanup slice that runs **after** the stage-body drain (it depends on
`refactor-drain-stages-apply`, which deletes `_legacy.py` and lands the drained
bodies in their cluster modules). Until the bodies are out of `_legacy`, the call
sites that consume these helpers do not yet live in the cluster modules, so
collapsing earlier would just relocate the churn.

## What Changes

- **Delete the five re-export aliases** (`_canonical_slug`, `_hash_parts`,
  `_quota_metric`, `_quota_limit`, `_remaining_amount`) from
  `composition_stages/_helpers.py`. After this, `_helpers.py` defines only the
  genuine cross-cluster helpers (`_effect_result`, `_adapter_stage`,
  `_not_implemented_stage`, `_omniroute_instance_id`).
- **Repoint the drained cluster call sites** (in `discovery.py`, `quota.py`,
  `access.py`, `probing.py`, `roles.py`, `apply.py`, …) to import the canonical
  names directly:
  - `from fmo.idempotency import canonical_slug, hash_parts`
  - `from fmo.quota_normalize import quota_limit, quota_metric, remaining_amount`
  and call them under their canonical (non-underscore) names, dropping the local
  `_`-prefixed aliasing introduced during the drain.
- **Drop the `__init__.py` re-exports** of `_canonical_slug`, `_hash_parts`,
  `_quota_metric`, `_quota_limit`, `_remaining_amount` (no external consumer).
- **Update the oracle** `tests/test_runtime_documentation.py::
  test_timestamp_hash_and_quota_helpers_are_centralized`: the loop asserting
  `stage_helpers._<alias>` exists and resolves outside `_helpers` is replaced by
  an assertion that `_helpers` no longer defines those underscore aliases and that
  the cluster modules import the canonical `idempotency`/`quota_normalize` names.

## Impact

- **Affected specs:** `system-architecture` — MODIFY "Shared helpers have a single
  canonical definition" to add that stage cluster modules import the canonical
  helper name directly, with no per-package underscore re-export alias layer in
  `_helpers`.
- **Affected code:** `composition_stages/_helpers.py` (aliases removed),
  `composition_stages/__init__.py` (re-exports removed), the cluster modules that
  call slug/hash/quota-math helpers (imports repointed),
  `tests/test_runtime_documentation.py` (oracle updated).
- **No external surface change beyond the unused re-exports:** the removed
  `composition_stages._canonical_slug` & co. have no consumers outside the package.
- **Behavior-preservation oracle:** the full existing pytest suite passes
  unchanged — the canonical functions are byte-identical, only their import path
  inside the package changes.
- **Depends on** `refactor-drain-stages-apply` (the call sites must already live
  in cluster modules and `_legacy.py` must be gone). Builds on the archived
  `refactor-unify-shared-helpers`, which created the canonical definitions.
