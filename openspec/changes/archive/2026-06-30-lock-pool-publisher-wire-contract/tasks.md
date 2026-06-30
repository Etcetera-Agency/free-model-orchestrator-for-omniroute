# Implementation Tasks

- [x] Define the shared canonical `fmo-pools/v1` golden fixture (one example generation)
  checked into the repo and mirrored with the OmniRoute slice
  (`align-fmo-pools-contract-ingest`).
- [x] `src/fmo/pool_publisher.py::compose_pool_generation` — confirm/adjust the emitted
  shape to the canonical contract: `contract_version`, `demand`
  (`requests_per_day`, `consumers`, `workload_class`), `constraints`
  (`free_only`, `capabilities`, int `min_context_tokens`, `quality_band` intent with
  `relax: { max_delta, when }`), `tail` intent (`strategy`, `mode`, `compatibility`).
- [x] Capability emission: draw `constraints.capabilities` from the shared capability
  vocabulary OmniRoute matches `required_capabilities` against (endpoints / `api:*` /
  `thinking` / compat tokens), not free-form strings.
- [x] `quality_band.category`: map FMO metrics to category names OmniRoute's
  `getResolvedTaskFitness` recognizes; document the mapping next to `_quality_category`.
- [x] Keep payload-hash idempotency (`Idempotency-Key` = `stable_hash(generation)`);
  assert it is not the generation string.
- [x] Tests (`tests/test_pool_publisher.py`): composed payload validates against the
  golden fixture/schema; `capabilities` and `quality_band.category` use the shared
  vocabulary; idempotency key equals the payload hash. The conformance test SHALL fail
  if the emitted shape drifts from the fixture.
