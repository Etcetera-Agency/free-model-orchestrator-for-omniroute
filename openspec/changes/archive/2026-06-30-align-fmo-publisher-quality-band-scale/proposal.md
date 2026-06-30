# Change: Emit quality_band on the [0..1] score scale and a contract workload_class

## Why

OmniRoute resolves the band against `model_intelligence.score`, a normalized value in
`[0..1]` (capability `fmo-pool-rebalance`, "Model intelligence band resolution"). The
publisher emits the band on the wrong scale and an off-vocabulary class
(`src/fmo/pool_publisher.py`):

1. **Band scale mismatch.** `_quality_band` defaults `min=0.0, max=100.0` and passes
   `float(minimum)`/`float(maximum)` straight from the role's
   `minimum_quality_value`/`maximum_quality_value`. If a role expresses quality on a
   0-100 (or ELO) scale, every candidate score in `[0..1]` falls below `min`, so the
   OmniRoute band check is never in-band and the pool can only fill via relax/overflow or
   not at all. The default `max=100.0` itself is already outside the valid range.

2. **Off-vocabulary `workload_class`.** The publisher defaults `workload_class` to
   `"standard"`, which is not in the contract vocabulary (`light | chat | reasoning |
   tools`). OmniRoute's class-to-weight table has no `standard` key, so the per-pool
   weight hint silently falls back to the global factor.

## What Changes

- `src/fmo/pool_publisher.py` — `_quality_band` emits `min`/`max` as normalized scores in
  `[0..1]`: map the role's quality intent onto that scale (and validate the result is
  within `[0..1]`); drop the `max=100.0` default in favor of a `[0..1]`-valid default.
- Normalize/validate `workload_class` to the contract vocabulary (`light | chat |
  reasoning | tools`); map any legacy `"standard"` to the agreed default
  (`chat` ≈ global factor) rather than emitting an unknown string.
- Tighten the wire-contract conformance test so a band outside `[0..1]` or an
  off-vocabulary `workload_class` fails before publish (fail-closed).

## Impact

- **Capability**: `pool-spec-publisher` (Requirements "Publisher fills only FMO-owned
  fields", "Wire-contract conformance").
- **Coordinates with** OmniRoute slice `wire-fmo-pools-token-factor-learning` (which
  keys the weight table on this exact `workload_class` vocabulary).
- **Risk**: none to OmniRoute schema; this only corrects emitted values.
