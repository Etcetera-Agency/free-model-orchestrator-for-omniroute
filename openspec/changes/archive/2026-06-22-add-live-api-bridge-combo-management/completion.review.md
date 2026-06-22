# Completion Review

## Scope

Implemented the bridge/combo-management slice for FMO:

- OmniRoute bridge allows the minimum combo management surface FMO needs:
  `GET/HEAD/OPTIONS /api/combos` and `GET/PUT/HEAD/OPTIONS /api/combos/fmo-*`.
- OmniRoute bridge still blocks `/api/combos/test`, `/api/combos/auto`,
  `/api/combos/reorder`, `DELETE /api/combos/fmo-*`, and unrelated management
  routes.
- FMO combo apply and rollback use `PUT /api/combos/{id}` instead of stale
  `POST /api/combos/{id}` assumptions.
- Fresh OmniRoute fixtures were recaptured through `127.0.0.1:20129`; combo
  fixture now records `status=200` and `13` combos.
- Fixture/playbook and module docs now describe the exact combo API and bridge
  policy.

## Verification

- `.venv/bin/python -m pytest tests/test_omniroute_fixture_ingestion.py tests/test_omniroute_account_ingestion.py tests/test_live_quota_ingestion.py tests/test_omniroute_free_registry_ingestion.py tests/test_omniroute_catalog_ingestion.py tests/test_foundation.py::test_omniroute_client_put_carries_idempotency_key_and_is_not_retried tests/test_composition.py::test_apply_stage_mutates_fmo_combo_and_reports_real_smoke_signal tests/test_spec_coverage.py` -> `22 passed`.
- `.venv/bin/python -m pytest tests/test_omniroute_fixture_ingestion.py::test_live_combos_fixture_records_seeded_operator_state tests/test_foundation.py::test_omniroute_client_surfaces_combo_management_auth_failure tests/test_composition.py::test_apply_stage_mutates_fmo_combo_and_reports_real_smoke_signal tests/test_spec_coverage.py` -> `7 passed`.
- `.venv/bin/python -m pytest tests/test_spec_coverage.py` -> `4 passed`.
- FMO pytest now binds the three `omniroute-client::*` bridge scenarios:
  combo fixture replay covers forwarded management combo reads, a 403 transport
  test covers auth failures surfacing as auth failures, and apply coverage
  asserts `/api/combos/test` is not used.
- `/Users/theDay/.nvm/versions/node/v24.1.0/bin/openspec validate --all --strict` -> `38 passed`.
- `/Users/theDay/.nvm/versions/node/v24.1.0/bin/node --import tsx --test tests/unit/api-bridge-fmo-routes.test.ts` in `/Users/theDay/Hermes/OmniRoute` -> `5 passed`.
- Live `etc2nd-shlink` verification after rebuild:
  - invalid auth on `/api/combos` and `/api/combos/fmo-routing_fast` reaches
    OmniRoute auth and returns `403`;
  - `/api/combos/test`, `/api/combos/auto`, and `DELETE /api/combos/fmo-*`
    remain bridge-level `404`;
  - temporary manage key can read `/api/combos` with `status=200`, `13` combos,
    and the temp key row is deleted afterward.
- `git diff --check` passed for FMO and OmniRoute.

## Residual

None known for this slice.
