# Design — forecast-driven quality band + fallback ordering

## Current state (verified in code)

- Schema `roles` has `minimum_quality_metric text`, `minimum_quality_value
  numeric` (`reference/db/schema.sql:255`) — **no max**.
- `_quality_gate_eligibility` (`composition_stages.py:960`): if `min*` is NULL →
  `EligibilityDecision(True)`. No writer sets `min*` anywhere in `src/`, so the
  gate is a no-op today.
- `evaluate_quality_gate` (`src/fmo/quality.py`) compares `metrics[metric] <
  value` (lower bound only).
- `build_priority_combo` (`src/fmo/allocation.py:54`) → `sorted(..., key=score,
  reverse=True)` → smartest first.
- Forecast: `role_demand_forecasts.protected_requests` is the demand target
  consumed by `_allocation_stage`.
- Endpoint capacity = confirmed-free remaining (`endpoint_access_states.
  effective_remaining`), already used by `allocate_globally`.

## Seed anchor → band, set-once (pseudocode)

The seed is the model the operator placed in the combo. Anchor = its canonical
AA metric. Set-once so repeated rebalances don't drift; re-seeding re-anchors.

```python
def resolve_band(role, live_combo_members, aa_metrics, protected_demand,
                 capacity_of, *, metric, floor_delta):
    # 1) anchor: stable across reruns
    if role.minimum_quality_value is not None and role.maximum_quality_value is not None:
        anchor = (role.minimum_quality_value + role.maximum_quality_value) / 2  # persisted band
    elif len(live_combo_members) == 1:                 # exactly one model => (re)seed
        anchor = aa_metrics[canonical(live_combo_members[0])][metric]
    else:
        return None    # >1 member but no persisted band: cannot anchor -> skip rebalance, report

    # 2) widen band around the anchor until in-band confirmed-free capacity covers demand,
    #    bounded below by an adequacy floor; the seed may end up anywhere inside.
    lo = hi = anchor
    floor = anchor - floor_delta
    eligible = members_within(metric, lo, hi)          # canonical endpoints with lo<=AA<=hi
    while capacity(eligible, capacity_of) < protected_demand:
        widened = expand(lo, hi, floor=floor, ceiling=None)  # step out by next nearest AA, down to floor, up unbounded
        if widened == (lo, hi):
            break                                      # nothing left to add
        lo, hi = widened
        eligible = members_within(metric, lo, hi)

    return Band(metric=metric, min=lo, max=hi)         # persisted to roles.min/max
```

Notes:
- **max is not pinned to the seed.** Expansion is symmetric-ish around the anchor
  (driven by where free capacity actually is), so smarter-than-seed models can
  enter — they are simply ordered last (below).
- **Adequacy floor** prevents the band dipping into uselessly weak models even if
  capacity is short; below-floor stays excluded (role may go `degraded`).
- **Paid seed**: contributes only its AA metric to the anchor; it is filtered out
  of `members_within` because it is not confirmed-free.

The resolved `[min, max]` is written to `roles.minimum_quality_value` /
`roles.maximum_quality_value` (the previously-unwritten columns), so the existing
gate read path starts enforcing it.

## Quality gate with upper bound

```python
def evaluate_quality_gate(metrics, *, metric, min_value, max_value, ...):
    if index_version != current_version: return needs_recalibration
    if metric not in metrics:            return unverifiable (unless allow_unverified)
    v = metrics[metric]
    if v < min_value:  return below_gate
    if v > max_value:  return above_band   # NEW upper bound
    return passed
```

`_quality_gate_eligibility` passes both bounds; a NULL `max` keeps today's
min-only behavior for back-compat with any role that has only a floor.

## Ordering: smartest last (pseudocode)

```python
def build_priority_combo(role_id, endpoints, *, per_pool_cap, quality_of):
    # ascending by AA quality => weakest-eligible first (primary), smartest last (fallback)
    ordered = sorted(endpoints, key=lambda e: (quality_of(e), -e["latency_rank"]))
    #            ^ primary key: quality ascending
    #              tie-break: faster/more-reliable first among equal-quality
    picked, used_pools = [], set()
    for e in ordered:
        if role_id in HEAVY_ROLES and e["pool"] in used_pools:
            continue
        picked.append(e["id"]); used_pools.add(e["pool"])
        if len(picked) == per_pool_cap: break
    return Combo(role_id, picked, strategy="priority")
```

This is the single inversion of the existing `reverse=True`. Membership is still
the band-filtered, score-eligible set; only the **order** changes so OmniRoute's
fallback chain escalates from cheap→smart.

## Demand-driven band requirement

The forecast already produces `protected_requests`. The new band-width helper
consumes it (above): the band is exactly wide enough to cover protected demand
with confirmed-free in-band capacity. This is why "the forecast computes the
band" — demand sets how far the band opens around the seed anchor.
