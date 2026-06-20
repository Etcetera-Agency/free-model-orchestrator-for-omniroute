## 1. Real Hermes source shapes

- [x] 1.1 Study NousResearch/hermes-agent @ v2026.6.5 for the real cron job,
  webhook subscription, profile and `state.db` sessions shapes.
- [x] 1.2 Record fixtures under `reference/fixtures/hermes/` from those shapes.

## 2. Parsers

- [x] 2.1 `parse_cron_jobs`, `parse_webhook_subscriptions`, `parse_profiles`.
- [x] 2.2 `observe_session_demand` (observed `calls_per_run` per combo/role from
  the real `sessions` DDL).
- [x] 2.3 `build_hermes_inventory` and `read_hermes_home`.

## 3. Validation

- [x] 3.1 `tests/test_hermes_inventory_real_shapes.py` green.
- [x] 3.2 `openspec validate add-hermes-inventory-real-shapes --strict` passes.
