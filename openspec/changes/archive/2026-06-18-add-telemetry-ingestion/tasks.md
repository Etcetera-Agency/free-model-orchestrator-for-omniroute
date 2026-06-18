## 1. Live telemetry fetch

- [x] 1.1 Failing test: telemetry sync fetches usage/latency/failure data from
  the configured OmniRoute/runtime source.
- [x] 1.2 Failing test: an unavailable telemetry source is handled conservatively
  (no fabricated metrics).
- [x] 1.3 Implement the fetch and normalization of the real shapes.

## 2. Fixtures

- [x] 2.1 Record realistic telemetry fixtures (OmniRoute analytics / Hermes
  sessions) and tests.

## 3. Validation

- [x] 3.1 `openspec validate add-telemetry-ingestion --strict` passes.
