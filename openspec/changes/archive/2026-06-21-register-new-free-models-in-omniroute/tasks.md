# Implementation Tasks (TDD)

Write each test first (red) → green → refactor. PostgreSQL real. OmniRoute
`POST /api/provider-models`, `GET /api/rate-limits` from recorded real shapes.

## Tasks

- [x] 1. TEST: a new confirmed-free model reachable via an existing connection
  and not yet an endpoint is registered via `POST /api/provider-models` with its
  provider + modelId → implement the registration step.
- [x] 2. TEST: a model already present as an endpoint is NOT re-registered
  (idempotent) → implement the existing-endpoint skip + idempotency key.
- [x] 3. TEST: a new free model whose provider has no connection is reported as
  `unreachable_new_free_model` and not registered → implement reachability gate.
- [x] 4. TEST: registration never issues PATCH/DELETE and never targets a paid
  model → assert additive, free-only behaviour.
- [x] 5. TEST: a registered model flows through matching → quota research →
  scoring → into a fitting existing combo on rebalance (no combo created) →
  verify ordering end-to-end.
- [x] 6. Bind tests with `@pytest.mark.spec("...")`, drop matching lines from
  `tests/spec_coverage_pending.txt`, run full `pytest` and
  `openspec validate register-new-free-models-in-omniroute --strict`.
