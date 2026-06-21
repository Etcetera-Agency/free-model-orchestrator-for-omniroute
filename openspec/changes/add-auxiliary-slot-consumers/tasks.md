# Implementation Tasks (TDD)

Write each test first (red) → green → refactor. Recorded real Hermes shapes
(`v2026.6.19`). PostgreSQL is real.

## Fixtures to reuse / extend

- `config.research.yaml` (from the previous slice): main + `auxiliary` with one
  explicit override + one `auto` slot.
- Add a second profile fixture whose auxiliary `vision` points at the **same**
  combo id as another profile, to exercise demand summing.
- A gateway-config fixture with a top-level `auxiliary` override.

## Tasks

- [ ] 1. TEST: a profile with `auxiliary.vision = {provider: omniroute, model:
  fmo-…}` emits an `auxiliary` consumer keyed `"{profile}:vision"` for that combo
  → implement auxiliary consumer emission in `parse_profiles`.
- [ ] 2. TEST: a slot with `provider: auto` or empty `model` emits **no**
  separate consumer (covered by the main combo) → implement the auto/empty skip.
- [ ] 3. TEST: a gateway-config top-level (or per-platform) `auxiliary` override
  emits an `auxiliary` consumer keyed `"gateway:…:slot"` →
  extend `parse_gateway_services`.
- [ ] 4. TEST: two slots in different profiles pointing at one combo produce a
  summed protected demand for that combo → verify through `aggregate_demand`.
- [ ] 5. Bind tests with `@pytest.mark.spec("...")`, drop matching lines from
  `tests/spec_coverage_pending.txt`, run full `pytest` and
  `openspec validate add-auxiliary-slot-consumers --strict`.
