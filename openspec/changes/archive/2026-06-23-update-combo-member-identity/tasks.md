# Implementation Tasks

## 1. TDD Coverage

- [x] 1.1 Add a failing allocation-stage test proving persisted
  `allocation_plans.targets` include structured combo member identity:
  `endpoint_id`, `combo_step`, quota pool, provider account, canonical model,
  and canonical family.
- [x] 1.2 Add a failing apply-stage test proving `PUT /api/combos/{id}` receives
  structured OmniRoute model steps with `providerId` and `connectionId` when the
  endpoint is account-pinned.
- [x] 1.3 Add a failing diff-stage test proving snapshots compare and persist
  structured `before`/`after` members while retaining endpoint ids for audit.
- [x] 1.4 Add a failing combo-builder test proving duplicate canonical model
  members are avoided when an eligible alternate exists.
- [x] 1.5 Add a failing combo-builder or allocation-stage test proving canonical
  family concentration is reported in `constraint_report`.
- [x] 1.6 Add a failing test proving quota pool capacity remains the hard gate
  even when model-family diversity would prefer another member.
- [x] 1.7 Bind all new scenarios with `@pytest.mark.spec(...)` and update
  `tests/spec_coverage_pending.txt` as tests land.

## 2. Implementation

- [x] 2.1 Extend allocation score-row queries to load provider id,
  OmniRoute connection id, provider account id, quota pool id, canonical model id,
  canonical slug, and canonical family.
- [x] 2.2 Add a small helper for building structured allocation targets from
  endpoint rows; keep endpoint id as the internal stable key.
- [x] 2.3 Update `build_priority_combo` to preserve endpoint ids while applying
  deterministic duplicate-canonical-model avoidance when safe alternatives exist.
- [x] 2.4 Persist family/provider/account concentration diagnostics in
  `constraint_report`.
- [x] 2.5 Update diff snapshots to store structured `before`/`after` combo member
  steps plus endpoint-id audit fields.
- [x] 2.6 Update apply to send structured `models` payloads and maintain existing
  drift guard, idempotency, smoke, rollback, and dry-run behavior.
- [x] 2.7 Add/update `AICODE-NOTE:` anchors around the member identity builder and
  structured apply path.

## 3. Verification

- [x] 3.1 Run targeted tests for allocation, apply, profile normalization, and
  smart advisory.
- [x] 3.2 Defer `.venv/bin/python -m pytest -q` to the final all-slice verification pass per operator instruction.
- [x] 3.3 Run OpenSpec validation when the CLI is available:
  `openspec validate update-combo-member-identity --strict`.
- [x] 3.4 Use Code Simplifier before finishing implemented slices.
- [x] 3.5 Update `openspec/TODO.md` if implementation or review discovers
  follow-up work.
