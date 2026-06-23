# Implementation Tasks

## 1. TDD Coverage

- [ ] 1.1 Add a failing allocation-stage test proving persisted
  `allocation_plans.targets` include structured combo member identity:
  `endpoint_id`, `combo_step`, quota pool, provider account, canonical model,
  and canonical family.
- [ ] 1.2 Add a failing apply-stage test proving `PUT /api/combos/{id}` receives
  structured OmniRoute model steps with `providerId` and `connectionId` when the
  endpoint is account-pinned.
- [ ] 1.3 Add a failing diff-stage test proving snapshots compare and persist
  structured `before`/`after` members while retaining endpoint ids for audit.
- [ ] 1.4 Add a failing combo-builder test proving duplicate canonical model
  members are avoided when an eligible alternate exists.
- [ ] 1.5 Add a failing combo-builder or allocation-stage test proving canonical
  family concentration is reported in `constraint_report`.
- [ ] 1.6 Add a failing test proving quota pool capacity remains the hard gate
  even when model-family diversity would prefer another member.
- [ ] 1.7 Bind all new scenarios with `@pytest.mark.spec(...)` and update
  `tests/spec_coverage_pending.txt` as tests land.

## 2. Implementation

- [ ] 2.1 Extend allocation score-row queries to load provider id,
  OmniRoute connection id, provider account id, quota pool id, canonical model id,
  canonical slug, and canonical family.
- [ ] 2.2 Add a small helper for building structured allocation targets from
  endpoint rows; keep endpoint id as the internal stable key.
- [ ] 2.3 Update `build_priority_combo` to preserve endpoint ids while applying
  deterministic duplicate-canonical-model avoidance when safe alternatives exist.
- [ ] 2.4 Persist family/provider/account concentration diagnostics in
  `constraint_report`.
- [ ] 2.5 Update diff snapshots to store structured `before`/`after` combo member
  steps plus endpoint-id audit fields.
- [ ] 2.6 Update apply to send structured `models` payloads and maintain existing
  drift guard, idempotency, smoke, rollback, and dry-run behavior.
- [ ] 2.7 Add/update `AICODE-NOTE:` anchors around the member identity builder and
  structured apply path.

## 3. Verification

- [ ] 3.1 Run targeted tests for allocation, apply, profile normalization, and
  smart advisory.
- [ ] 3.2 Run `.venv/bin/python -m pytest -q`.
- [ ] 3.3 Run OpenSpec validation when the CLI is available:
  `openspec validate update-combo-member-identity --strict`.
- [ ] 3.4 Use Code Simplifier before finishing implemented slices.
- [ ] 3.5 Update `openspec/TODO.md` if implementation or review discovers
  follow-up work.
