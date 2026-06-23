# Change: Unify duplicated helpers once the module boundaries exist

## Why

The analysis found the same small helpers reimplemented or parked in the wrong
module. With the persistence and stage packages split (slices
`refactor-split-persistence` and `refactor-split-stages-*`), the right homes now
exist, so this final cleanup slice consolidates duplicates behind one definition
each. This is deduplication only — every call site keeps identical behavior.

## What Changes

- **Row helpers:** `_one`, `_optional`, `_many`, `_jsonb`, `_content_hash` are
  defined once in `persistence/_base.py`; any ad-hoc reimplementation in stage
  modules is replaced by importing the base helper.
- **Timestamp helper:** the repeated `datetime.now(UTC)` pattern (47 sites,
  already modernized by the ruff `UP017` pass) is funneled through a single
  `utcnow()` helper (e.g. in `idempotency.py` or a small `_time` module).
- **Slug / hash / idempotency keys:** `_canonical_slug`, `_hash_parts`, and the
  combo idempotency-key builder are consolidated into the existing
  `idempotency.py`; `composition_stages/_helpers.py` imports them rather than
  redefining.
- **Quota math:** `_quota_metric`, `_quota_limit`, `_remaining_amount` move from
  the stage helpers next to `quota_normalize.py` / `quota_manager.py` where the
  rest of the quota math lives, and the stage modules import them from there.

## Impact

- Affected specs: `system-architecture` (ADDED structural requirement)
- Affected code: `src/fmo/persistence/_base.py`, `src/fmo/idempotency.py`,
  `src/fmo/quota_normalize.py` / `quota_manager.py`,
  `src/fmo/composition_stages/_helpers.py`, plus the call sites that switch to
  the canonical import. Oracle: the full pytest suite passes unchanged; no new
  behavior, only one definition per helper.
- Depends on `refactor-split-persistence` and the three `refactor-split-stages-*`
  slices (their target modules must exist first).
