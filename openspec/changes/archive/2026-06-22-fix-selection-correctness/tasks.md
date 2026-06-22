## 1. Production scoring uses real component inputs

- [x] 1.1 Write failing test: `role-scoring` stage derives `benchmark_fit` from
      `aa_subscore` over persisted AA metrics (low/mid/high produce distinct
      totals), bound to `role-scorer::AA quality drives the benchmark component`.
- [x] 1.2 Write failing test: `latency` component uses `latency_score_source`
      precedence (endpoint p95 → provider p95 → AA latency), bound to
      `role-scorer::Latency component uses the latency source priority`.
- [x] 1.3 Write failing test: `health` and `stability` come from persisted
      `endpoint_health_observations` (degraded telemetry lowers the score), bound
      to `role-scorer::Health and stability come from telemetry observations`.
- [x] 1.4 Write failing test: missing AA metrics apply the uncertainty penalty
      rather than a full 1.0, bound to `role-scorer::Missing AA metrics apply the
      uncertainty penalty`.
- [x] 1.5 Wire `_role_scoring_stage` to read AA/telemetry rows and feed
      `aa_subscore`, `latency_score_source`, health/stability into
      `score_endpoint`; remove the constant `1.0` placeholders.

## 2. Shared-pool remaining counted once

- [x] 2.1 Write failing test: live quota for an account is not duplicated as
      independent per-endpoint capacity, bound to `quota-manager::Account
      remaining is not duplicated per endpoint`.
- [x] 2.2 Write failing test: the sum of a pool's endpoints' allocations cannot
      exceed the pool remaining, bound to `quota-manager::Pool capacity bounds the
      sum of member allocations`.
- [x] 2.3 Change `_quota_sync_stage` / allocation inputs so endpoint capacity is
      derived from the shared pool remaining, not the per-endpoint copy.

## 3. Allocation reserves capacity for all combo members

- [x] 3.1 Write failing test: a fallback combo member reserves its pool capacity
      during global allocation, bound to `allocator::Fallback members reserve
      their pool capacity`.
- [x] 3.2 Write failing test: a would-be combo member with no remaining pool
      capacity is dropped from the combo, bound to `allocator::Combo member
      without pool capacity is dropped`.
- [x] 3.3 Extend `allocate_globally` / `build_priority_combo` so every emitted
      member is reserved against its pool and the oversubscription gate sees the
      full reservation.

## 4. Close out

- [x] 4.1 Run targeted pytest (full suite deferred to end of batch per operator instruction).
- [x] 4.2 Remove the now-bound scenarios from `tests/spec_coverage_pending.txt`
      and `EXPECTED_ACTIVE_PENDING` in `tests/test_runtime_documentation.py`.
- [x] 4.3 `openspec validate fix-selection-correctness --strict`.
