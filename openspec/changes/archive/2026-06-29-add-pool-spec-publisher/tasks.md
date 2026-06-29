# Implementation Tasks

- [x] Add `build_publisher_stages()` in `composition.py` (hermes-inventory → role-lifecycle → demand-forecast → compose → publish → usage-feedback); reuse `PipelineRunner` unchanged.
- [x] Add `compose()` producing the `fmo-pools/v1` payload from roles + demand + `role -> pool_id`; reject a pool missing `min_context_tokens` (fail closed).
- [x] Add `publish()`: gate contract acceptance via the version gate, `client.put("/api/fmo/pools", ...)` with `Idempotency-Key = stable_hash(canonical_payload)`, `audit_change`, store in `published_generations`.
- [x] Add `usage-feedback` step: `GET /api/fmo/usage` → recalibrate next-cycle demand inputs.
- [x] Add `published_generations` table (generation PK, payload_hash, payload_json, status, acked_at).
- [x] demand-forecast: keep `aggregate_demand`/`protected_demand`/`apply_historical_reserve`/`cold_start_demand`; remove `quality_band_for_demand` capacity coupling; source band intent from role policy.
- [x] omniroute-client: repoint writes to `PUT /api/fmo/pools`; change version gate to gate `fmo-pools/v1` contract acceptance.
- [x] Tests: publisher emits a valid `fmo-pools/v1` payload from a seeded inventory; missing `min_context_tokens` fails closed; same payload reuses the same idempotency key; changed payload with reused generation marker gets a new idempotency key; version gate rejects unsupported contract; band is intent-only (no capacity read).
