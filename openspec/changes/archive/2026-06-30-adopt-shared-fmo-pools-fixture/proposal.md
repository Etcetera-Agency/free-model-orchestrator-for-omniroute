# Change: Adopt the single shared contract fixture and integer requests_per_day

## Why

The `lock-pool-publisher-wire-contract` change added a conformance test, but it asserts
against FMO's **own** fixture, not a fixture shared with OmniRoute. The two repos ended
up with divergent fixtures (FMO `consumers: 3` vs OmniRoute `consumers: ["hermes"]`), so
neither conformance test validates the same contract — the drift guard does not actually
guard. OmniRoute is correcting its `consumers` type to a numeric count (per concept §4)
in `fix-fmo-pools-contract-consumers-and-fixture`; this change makes FMO adopt the one
canonical fixture and removes the last shape mismatch from the FMO side.

Also, the publisher emits `demand.requests_per_day` as a float (`float(demand)`); the
OmniRoute ingester accepts numbers, but the canonical fixture and the demand contract are
whole request counts. Emit an integer count to keep the wire shape clean and the fixture
byte-stable.

## What Changes

- `reference/fixtures/fmo-pools-v1-generation.json` — replace with the canonical shared
  fixture, byte-identical to OmniRoute's copy (`consumers: 4`, whole-number
  `requests_per_day`).
- `src/fmo/pool_publisher.py::compose_pool_generation` — emit
  `demand.requests_per_day` as an integer count (round/int the forecast) while keeping
  `consumers` as the integer count it already emits.
- `tests/test_pool_publisher.py` — the conformance test loads the shared fixture (not a
  private one) and asserts the composed payload matches that fixture's shape; assert
  `requests_per_day` is an integer and `consumers` is an integer count.

## Impact

- **Capability**: `pool-spec-publisher` (modifies "Wire-contract conformance").
- **Reused**: `compose_pool_generation`, the capability/category vocabulary alignment,
  payload-hash idempotency.
- **Net-new**: nothing structural — this aligns the fixture and the numeric type.
- **Pairs with**: OmniRoute `fix-fmo-pools-contract-consumers-and-fixture` (same fixture
  bytes; numeric `consumers`). Together they make the seam round-trip.
