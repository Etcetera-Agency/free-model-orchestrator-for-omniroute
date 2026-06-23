## 1. Oracles

- [x] 1.1 Write failing test: the row helpers (`_one`, `_optional`, `_many`,
      `_jsonb`, `_content_hash`) have a single definition in `persistence/_base`
      and are not reimplemented in stage modules, bound to
      `system-architecture::Row access helpers are defined once in the persistence base`.
- [x] 1.2 Write failing test: timestamp (`utcnow`), slug/hash, and quota-math
      helpers each have one canonical definition and call sites import it, bound
      to `system-architecture::Timestamp and hashing helpers are centralized`.

## 2. Consolidate

- [x] 2.1 Point any ad-hoc row-helper reimplementation at `persistence/_base`.
- [x] 2.2 Introduce a single `utcnow()` helper; replace the inline
      `datetime.now(UTC)` sites with it.
- [x] 2.3 Move `_canonical_slug`, `_hash_parts`, and the combo idempotency-key
      builder into `idempotency.py`; import them from `composition_stages/_helpers`.
- [x] 2.4 Move `_quota_metric`, `_quota_limit`, `_remaining_amount` next to
      `quota_normalize`/`quota_manager`; import them in the stage modules.

## 3. Close out

- [x] 3.1 `make check` clean (vulture confirms no helper left orphaned).
- [x] 3.2 Full `pytest` passes unchanged.
- [x] 3.3 Remove the two bound scenarios from `tests/spec_coverage_pending.txt`
      and `EXPECTED_ACTIVE_PENDING`.
- [x] 3.4 `openspec validate refactor-unify-shared-helpers --strict`.
