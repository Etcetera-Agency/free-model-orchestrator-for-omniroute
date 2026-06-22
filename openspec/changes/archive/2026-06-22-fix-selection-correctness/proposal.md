# Change: Make role scoring, pool capacity, and allocation reservation correct

## Why

The production composition collects AA benchmarks, telemetry health/latency, and
per-account live quota, but the selection path does not actually consume them:

- `_role_scoring_stage` hardcodes `benchmark_fit=1.0, health=1.0, latency=1.0,
  stability=1.0` (`src/fmo/composition_stages.py:1092`), so only `capability_fit`
  and `quota_headroom` vary. The real primitives in `src/fmo/scoring.py`
  (`aa_subscore`, `latency_score_source`, `_normalize`) are never wired in, so
  combo ordering does not reflect quality, health, or latency.
- `_quota_sync_stage` writes the account-level remaining onto every endpoint of
  that account (`src/fmo/composition_stages.py:887`), so each endpoint looks like
  it independently owns the full account quota. Scoring `quota_headroom` and the
  allocator's per-endpoint `capacity` then over-count shared capacity.
- `allocate_globally` reserves pool capacity for only the first fitting endpoint
  per role (`src/fmo/allocation.py:50`), while `build_priority_combo` emits up to
  `per_pool_cap` scored members plus a router tail. Secondary combo members are
  never capacity-checked against their pools, so an emitted combo can promise
  capacity the pool does not have.

Together these break the stated invariant that capacity is global, shared, and
quality-ordered.

## What Changes

- Production `role-scoring` derives `benchmark_fit` from `aa_subscore`, `latency`
  from `latency_score_source` over persisted telemetry/AA, and `health` /
  `stability` from telemetry health observations — no constant `1.0` placeholders.
- Account/pool remaining is counted once per quota pool; an account's endpoints
  share one pool capacity instead of each claiming the full account remaining.
- **BREAKING** (allocation semantics): global allocation reserves pool capacity
  for every endpoint that becomes a combo member (primary and fallback), not only
  the primary; a member that would exceed remaining pool capacity is dropped from
  the combo.

## Impact

- Affected specs: `role-scorer`, `quota-manager`, `allocator`
- Affected code: `src/fmo/composition_stages.py` (`_role_scoring_stage`,
  `_quota_sync_stage`, `_allocation_stage`), `src/fmo/allocation.py`,
  `src/fmo/scoring.py` (already provides the primitives), pipeline scoring/
  allocation tests.
