# Implementation Tasks (TDD)

Write tests first (red) -> green -> refactor. Mock only the network boundary
with recorded OmniRoute management shapes or source-derived exact shapes from
`../OmniRoute/src/app/api/combos`. Do not call human run or live mutation
commands without operator approval.

## 1. Specification

- [x] 1.1 Add `omniroute-client` requirements for management combo route
  forwarding through the live API bridge.
- [x] 1.2 Add `combo-applier` requirements for reading/writing combos through
  management API routes, never `/v1/combos`.
- [x] 1.3 Track executable-test follow-up in `tests/spec_coverage_pending.txt`.
- [x] 1.4 Validate the OpenSpec change strictly.

## 2. Implementation

- [x] 2.1 TEST: `GET /api/combos` through the bridge reaches OmniRoute
  management auth/handler and does not return a bridge-level `404`.
- [x] 2.2 TEST: missing or invalid management auth on `/api/combos*` returns
  the OmniRoute auth failure, not a bridge-level `404`.
- [x] 2.3 TEST: `/api/combos/test` remains blocked by FMO/bridge policy.
- [x] 2.4 TEST: combo apply reads live combo state through
  `GET /api/combos` on the shared OmniRoute client pointed at the bridge.
- [x] 2.5 TEST: combo apply updates an existing combo through the OmniRoute
  management combo write route under `/api/combos/{id}` with management auth,
  preserving drift, smoke, rollback, and rebalance-only behavior.
- [x] 2.6 TEST: combo apply never calls `/v1/combos` or any public combo
  projection for management reads/writes.
- [x] 2.7 TEST: existing combo-update and rollback tests use the live
  OmniRoute verb (`PUT /api/combos/{id}`) so stale `POST` assumptions fail.
- [x] 2.8 Implement the bridge allowlist/policy for the management combo routes
  required by FMO, without exposing unrelated management routes.
- [x] 2.9 Align the FMO combo writer with the live OmniRoute management route
  shape and verb from `../OmniRoute/src/app/api/combos/[id]/route.ts`.
- [x] 2.10 Add or update docs/playbook notes with the before/after live
  verification commands and expected status classes for `/api/combos*`.
- [x] 2.11 Run targeted pytest for the new executable specs,
  `openspec validate add-live-api-bridge-combo-management --strict`, and live
  read-only verification against `127.0.0.1:20129`.
- [x] 2.12 Remove covered `combo-applier::*` entries from
  `tests/spec_coverage_pending.txt`; keep `omniroute-client::*` bridge entries
  pending because their executable coverage lives in the OmniRoute fork unit
  suite rather than FMO pytest markers.
