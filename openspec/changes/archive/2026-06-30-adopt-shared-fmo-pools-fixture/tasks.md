# Implementation Tasks

- [x] Replace `reference/fixtures/fmo-pools-v1-generation.json` with the canonical shared
  fixture — byte-identical to the OmniRoute copy
  (`tests/fixtures/fmo/fmo-pools-v1.golden.json`):

  ```json
  {
    "contract_version": "fmo-pools/v1",
    "generation": "gen-001",
    "generated_at": "2026-06-29T00:00:00.000Z",
    "pools": [
      {
        "pool_id": "pool-fast",
        "combo_id": "combo-fast",
        "demand": { "requests_per_day": 1000, "consumers": 4, "workload_class": "reasoning" },
        "constraints": {
          "free_only": true,
          "capabilities": ["api:openai", "chat", "thinking", "tool_call"],
          "min_context_tokens": 32768,
          "quality_band": {
            "source": "model_intelligence",
            "metric": "score",
            "category": "coding",
            "min": 55,
            "max": 85,
            "relax": { "max_delta": 12, "when": "underfilled" }
          }
        },
        "tail": { "strategy": "auto", "mode": "fallback", "compatibility": "strict" }
      }
    ]
  }
  ```

- [x] `src/fmo/pool_publisher.py::compose_pool_generation` — emit
  `demand.requests_per_day` as an integer count (`int(round(...))`); keep `consumers` as
  the integer count it already emits.
- [x] `tests/test_pool_publisher.py` — point the conformance test at the shared fixture
  (not a private one); assert the composed payload's shape matches it, that
  `requests_per_day` is `int`, and that `consumers` is an integer count. Assert the FMO
  fixture file equals the OmniRoute fixture bytes (or document the sync mechanism).
- [x] Keep payload-hash idempotency (`Idempotency-Key` = `stable_hash(generation)`).
