# Implementation Tasks

- [x] `src/fmo/pool_publisher.py` `_quality_band` — emit `min`/`max` as normalized scores
      in `[0..1]`; map the role's quality intent onto that scale; replace the `max=100.0`
      default with a `[0..1]`-valid default; assert `0 <= min <= max <= 1`.
- [x] Normalize `workload_class` to `{light, chat, reasoning, tools}`; map legacy
      `"standard"` (and unknown values) to the agreed default; never emit an
      off-vocabulary class.
- [x] `tests/test_pool_publisher.py` — assert emitted band is within `[0..1]`; assert
      `workload_class` is always in the contract vocabulary; a role with a 0-100 intent is
      rescaled, not passed through; composition fails closed on an un-mappable band.
- [x] Confirm the shared `fmo-pools/v1` fixture (cross-repo) still validates against the
      OmniRoute schema after the value changes.
