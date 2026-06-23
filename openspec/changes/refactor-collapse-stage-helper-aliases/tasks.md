## 1. Oracle

- [ ] 1.1 Update the failing test
      `tests/test_runtime_documentation.py::test_timestamp_hash_and_quota_helpers_are_centralized`:
      replace the loop over `("_canonical_slug", "_hash_parts", "_quota_metric",
      "_quota_limit", "_remaining_amount")` (which currently asserts each exists on
      `fmo.composition_stages._helpers` and resolves outside `_helpers`) with an
      assertion that **none** of those underscore aliases are defined on `_helpers`
      and that the cluster modules import the canonical `canonical_slug`/
      `hash_parts`/`quota_metric`/`quota_limit`/`remaining_amount` names from
      `fmo.idempotency` / `fmo.quota_normalize`. Bound to
      `system-architecture::Shared helpers have a single canonical definition`.

## 2. Collapse the aliases

- [ ] 2.1 Remove the `_canonical_slug = canonical_slug` … `_remaining_amount =
      remaining_amount` block (and now-unused alias imports) from
      `composition_stages/_helpers.py`; leave only the genuine cross-cluster
      helpers (`_effect_result`, `_adapter_stage`, `_not_implemented_stage`,
      `_omniroute_instance_id`).
- [ ] 2.2 Repoint every drained cluster call site to the canonical names:
      `from fmo.idempotency import canonical_slug, hash_parts` and
      `from fmo.quota_normalize import quota_limit, quota_metric, remaining_amount`,
      calling them without the `_` prefix (including the `_remaining_requests`
      alias in `probing.py`, sourced from `quota_normalize.remaining_amount`).
- [ ] 2.3 Remove the `from ._helpers import _canonical_slug …` re-export lines for
      the five helpers from `composition_stages/__init__.py`.

## 3. Close out

- [ ] 3.1 Grep `src/` and `tests/` for any residual underscore-aliased helper
      reference (`_canonical_slug`, `_hash_parts`, `_quota_metric`, `_quota_limit`,
      `_remaining_amount`) and confirm none remain outside their canonical modules.
- [ ] 3.2 `make check` clean.
- [ ] 3.3 Run the full pytest suite under both entry points as the
      behavior-preservation oracle.
- [ ] 3.4 `git diff --check`; `openspec validate refactor-collapse-stage-helper-aliases --strict`.
