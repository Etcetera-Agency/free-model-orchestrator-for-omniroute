## 1. Oracles

- [ ] 1.1 Write failing test: the row helpers (`_one`, `_optional`, `_many`,
      `_jsonb`, `_content_hash`) have a single definition in `persistence/_base`
      and are not reimplemented in stage modules, bound to
      `system-architecture::Row access helpers are defined once in the persistence base`.
- [ ] 1.2 Write failing test: timestamp (`utcnow`), slug/hash, and quota-math
      helpers each have one canonical definition and call sites import it, bound
      to `system-architecture::Timestamp and hashing helpers are centralized`.

## 2. Consolidate

- [ ] 2.1 Point any ad-hoc row-helper reimplementation at `persistence/_base`.
- [ ] 2.2 Introduce a single `utcnow()` helper; replace the inline
      `datetime.now(UTC)` sites with it.
- [ ] 2.3 Move `_canonical_slug`, `_hash_parts`, and the combo idempotency-key
      builder into `idempotency.py`; import them from `composition_stages/_helpers`.
- [ ] 2.4 Move `_quota_metric`, `_quota_limit`, `_remaining_amount` next to
      `quota_normalize`/`quota_manager`; import them in the stage modules.

## 3. Close out

- [ ] 3.1 `make check` clean (vulture confirms no helper left orphaned).
- [ ] 3.2 Full `pytest` passes unchanged.
- [ ] 3.3 Remove the two bound scenarios from `tests/spec_coverage_pending.txt`
      and `EXPECTED_ACTIVE_PENDING`.
- [ ] 3.4 `openspec validate refactor-unify-shared-helpers --strict`.
